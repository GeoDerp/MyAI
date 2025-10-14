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
    cache_set(fingerprint, out)
    out["fingerprint"] = fingerprint
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
    content_hash = ""
    if source_text:
        content_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

    fingerprint = make_fingerprint(
        doi,
        model_id or "",
        prompt_fingerprint or "",
        content_hash,
        json.dumps(condensation_config, sort_keys=True),
        str(max_tokens),
    )

    existing = cache_get(fingerprint)
    if existing:
        return existing

    # Use extractive summarization to produce a condensed summary and meta.
    try:
        from .condense import extractive_summarize
    except Exception:
        # fallback to placeholder if condense module unavailable
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

    # If we have source_text, condense it; otherwise use DOI metadata as placeholder
    source = source_text or ""
    summary_text, summ_meta = extractive_summarize(source, max_tokens)
    out = {
        "doi": doi,
        "summary": summary_text,
        "meta": {
            "config": condensation_config,
            "max_tokens": max_tokens,
            "model_id": model_id,
            "prompt_fingerprint": prompt_fingerprint,
            "content_hash": content_hash,
            "summarizer": "extractive",
            **summ_meta,
        },
    }
    cache_set(fingerprint, out)
    out["fingerprint"] = fingerprint
    return out


def get_by_doi_model_prompt(doi: str, model_id: str, prompt_fingerprint: str, max_tokens: int, condensation_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fp = make_fingerprint(doi, model_id or "", prompt_fingerprint or "", json.dumps(condensation_config, sort_keys=True), str(max_tokens))
    return cache_get(fp)
