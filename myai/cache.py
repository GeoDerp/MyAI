"""
Simple caching utilities for condensed summaries.

Provides a file-backed cache (JSON files inside `.cache/summaries`) and an
in-memory fallback. Exposes:
- cache_get(key) -> Optional[dict]
- cache_set(key, value) -> None
- make_fingerprint(*parts) -> str
- summarize_document(doi, condensation_config, max_tokens) -> dict

This first implementation focuses on durable summaries keyed by a fingerprint
and is intentionally small so it can be extended later (Redis/S3 backends).
"""
from __future__ import annotations

import os
import json
import hashlib
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Optional Redis backend
REDIS_URL = os.environ.get("REDIS_URL")
_redis_client = None
try:
    if REDIS_URL:
        import redis as _redis
        _redis_client = _redis.from_url(REDIS_URL)
except Exception as e:
    logger.debug("Redis not configured or import failed: %s", e)


def verify_redis_connection(timeout: float = 1.0) -> bool:
    """Return True if Redis is configured and a ping succeeds.

    This is intended as a lightweight runtime check callers can use to
    determine whether Redis-based caching is active.
    """
    global _redis_client
    if _redis_client is None:
        return False
    try:
        # small timeout-friendly ping; redis-py handles this internally
        return _redis_client.ping()
    except Exception:
        return False

CACHE_DIR = os.path.join(os.getcwd(), ".cache", "summaries")
os.makedirs(CACHE_DIR, exist_ok=True)


def _key_to_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def make_fingerprint(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        if p is None:
            p = ""
        h.update(p.encode("utf-8"))
    return h.hexdigest()


def cache_get(key: str) -> Optional[Dict[str, Any]]:
    # If Redis configured, try Redis first
    if _redis_client is not None:
        try:
            val = _redis_client.get(key)
            if val is None:
                return None
            if isinstance(val, bytes):
                val = val.decode("utf-8")
            return json.loads(val)
        except Exception:
            # fallback to file-based
            pass

    path = _key_to_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cache_set(key: str, value: Dict[str, Any]) -> None:
    # Try Redis if available
    if _redis_client is not None:
        try:
            _redis_client.set(key, json.dumps(value, ensure_ascii=False))
            return
        except Exception:
            pass

    path = _key_to_path(key)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False)


def summarize_document(doi: str, condensation_config: Dict[str, Any], max_tokens: int = 2000) -> Dict[str, Any]:
    """Produce (or load) a condensed summary for a DOI.

    For now this is a thin wrapper: it computes a fingerprint from DOI +
    condensation_config + max_tokens, returns cached summary if present, or
    creates a trivial placeholder summary and caches it.
    """
    fingerprint = make_fingerprint(doi, json.dumps(condensation_config, sort_keys=True), str(max_tokens))
    existing = cache_get(fingerprint)
    if existing:
        # Older cache entries may not include the fingerprint key. Ensure the
        # returned shape always contains the fingerprint for caller convenience.
        if isinstance(existing, dict) and "fingerprint" not in existing:
            existing["fingerprint"] = fingerprint
        return existing

    # Placeholder condensation: in real pipeline we'd chunk, embed, and summarize.
    summary_text = f"[condensed summary for {doi} with max_tokens={max_tokens}]"
    out = {
        "doi": doi,
        "summary": summary_text,
        "meta": {
            "config": condensation_config,
            "max_tokens": max_tokens,
        }
    }
    # Ensure the fingerprint is part of the object saved to cache so subsequent
    # reads return the same shape (tests expect a 'fingerprint' key).
    out["fingerprint"] = fingerprint
    cache_set(fingerprint, out)
    return out


def cache_exists(key: str) -> bool:
    if _redis_client is not None:
        try:
            return _redis_client.exists(key) == 1
        except Exception:
            pass
    return os.path.exists(_key_to_path(key))


def cache_invalidate(key: str) -> bool:
    """Delete a cache entry by key. Returns True if removed."""
    # Try Redis first
    try:
        if _redis_client is not None:
            res = _redis_client.delete(key)
            return res == 1
    except Exception:
        pass

    path = _key_to_path(key)
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        pass
    return False


def summarize_document_with_content(
    doi: str,
    condensation_config: Dict[str, Any],
    max_tokens: int = 2000,
    model_id: str = "unknown",
    prompt_fingerprint: str | None = None,
    source_text: str | None = None,
) -> Dict[str, Any]:
    """Summarize using DOI + model + prompt + content to create fingerprint.

    This computes a fingerprint composed of DOI, model_id, prompt_fingerprint,
    a content hash (if source_text provided), and the condensation_config and
    max_tokens. If a cached summary exists it is returned. Otherwise a placeholder
    summary is created and saved.
    """
    # New options for chunking/condensation. These can be overridden via
    # condensation_config or passed in to control behavior.
    chunk_size_tokens = int(condensation_config.get("chunk_size_tokens", 1000))
    chunk_overlap_tokens = int(condensation_config.get("chunk_overlap_tokens", 100))
    per_chunk_summary_tokens = int(condensation_config.get("per_chunk_summary_tokens", 300))
    condense_strategy = condensation_config.get("condense_strategy", "extractive")
    force_recompute = bool(condensation_config.get("force_recompute", False))

    content_hash = ""
    if source_text:
        content_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    # Fingerprint includes chunking & strategy parameters so different
    # condensation configs produce distinct cached entries.
    fingerprint = make_fingerprint(
        doi,
        model_id or "",
        prompt_fingerprint or "",
        content_hash,
        json.dumps(condensation_config, sort_keys=True),
        str(max_tokens),
        str(chunk_size_tokens),
        str(chunk_overlap_tokens),
        str(per_chunk_summary_tokens),
        str(condense_strategy),
    )

    if not force_recompute:
        existing = cache_get(fingerprint)
        if existing:
            return existing

    # Prefer local extractive summarizer
    try:
        from .condense import extractive_summarize, split_sentences, estimate_tokens
    except Exception:
        # fallback to previous placeholder behavior if condense module unavailable
        summary_text = (
            f"[condensed summary for {doi} | model={model_id} | prompt_fp={prompt_fingerprint} | content_hash={content_hash[:8]}]"
        )
        out = {
            "doi": doi,
            "summary": summary_text,
            "meta": {
                "config": condensation_config,
                "max_tokens": max_tokens,
                "model_id": model_id,
                "prompt_fingerprint": prompt_fingerprint,
                "content_hash": content_hash,
            },
        }
        cache_set(fingerprint, out)
        out["fingerprint"] = fingerprint
        return out

    # If there's no source text, keep the old placeholder behavior
    if not source_text:
        summary_text, summ_meta = extractive_summarize("", max_tokens)
        out = {
            "doi": doi,
            "summary": summary_text,
            "meta": {
                "config": condensation_config,
                "max_tokens": max_tokens,
                "model_id": model_id,
                "prompt_fingerprint": prompt_fingerprint,
                "content_hash": content_hash,
                "summarizer": condense_strategy,
                **summ_meta,
            },
        }
        cache_set(fingerprint, out)
        out["fingerprint"] = fingerprint
        return out

    # Chunk the source_text into chunks of ~chunk_size_tokens (using sentence boundaries)
    sentences = split_sentences(source_text)
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for i, s in enumerate(sentences):
        t = estimate_tokens(s)
        # If single sentence larger than chunk_size, still include it
        if current_tokens + t > chunk_size_tokens and current:
            chunks.append(" ".join(current))
            # prepare next chunk with overlap
            if chunk_overlap_tokens > 0:
                # include trailing sentences to create overlap
                overlap = []
                overlap_tokens = 0
                # walk backwards through current to add overlap until tokens reached
                for ss in reversed(current):
                    overlap_tokens += estimate_tokens(ss)
                    if overlap_tokens > chunk_overlap_tokens:
                        break
                    overlap.insert(0, ss)
                current = overlap.copy()
                current_tokens = sum(estimate_tokens(x) for x in current)
            else:
                current = []
                current_tokens = 0

        current.append(s)
        current_tokens += t

    if current:
        chunks.append(" ".join(current))

    chunk_summaries: list[dict] = []
    for idx, ch in enumerate(chunks):
        # Condense each chunk to per_chunk_summary_tokens using extractive summarizer
        summ_text, summ_meta = extractive_summarize(ch, per_chunk_summary_tokens)
        chunk_summaries.append({
            "index": idx,
            "orig_tokens": estimate_tokens(ch),
            "summary": summ_text,
            "meta": summ_meta,
        })

    # Combine chunk summaries and perform a final condensation to fit max_tokens
    combined = "\n".join(c.get("summary", "") for c in chunk_summaries)
    final_summary, final_meta = extractive_summarize(combined, max_tokens)

    out = {
        "doi": doi,
        "summary": final_summary,
        "meta": {
            "config": condensation_config,
            "max_tokens": max_tokens,
            "model_id": model_id,
            "prompt_fingerprint": prompt_fingerprint,
            "content_hash": content_hash,
            "summarizer": condense_strategy,
            "chunk_count": len(chunks),
            "chunks": chunk_summaries,
            **final_meta,
        },
    }
    cache_set(fingerprint, out)
    out["fingerprint"] = fingerprint
    return out


def get_by_doi_model_prompt(doi: str, model_id: str, prompt_fingerprint: str, max_tokens: int, condensation_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fp = make_fingerprint(doi, model_id or "", prompt_fingerprint or "", json.dumps(condensation_config, sort_keys=True), str(max_tokens))
    return cache_get(fp)
