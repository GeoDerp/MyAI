from __future__ import annotations

from typing import List, Dict, Any
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)
import re
import difflib as _difflib
try:
    # Optional semantic similarity: sentence-transformers
    from sentence_transformers import SentenceTransformer
    import numpy as _np
    from numpy.linalg import norm as _norm
    _HAS_ST = True
    _ST_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
except Exception:
    _HAS_ST = False
    _ST_MODEL = None
    # numpy may not be available either; fallback variables
    _np = None
    _norm = None

# Embedding cache: prefer Redis (if redis package and REDIS_URL present), else in-memory LRU
try:
    import redis as _redis
    _REDIS_URL = __import__('os').environ.get('REDIS_URL') or __import__('os').environ.get('MYAI_REDIS_URL')
    if _REDIS_URL:
        _redis_client = _redis.from_url(_REDIS_URL)
    else:
        _redis_client = None
except Exception:
    _redis_client = None

from functools import lru_cache

@lru_cache(maxsize=1024)
def _encode_cached(text: str):
    """In-memory fallback encoder cache. Returns embedding vector or None."""
    if not _HAS_ST or _ST_MODEL is None:
        return None
    try:
        emb = _ST_MODEL.encode([text])[0]
        return emb
    except Exception:
        return None

def _get_embedding(text: str):
    """Get embedding from Redis cache or in-memory; returns vector or None."""
    if not text:
        return None
    key = f"claim_emb:{hash(text)}"
    if _redis_client:
        try:
            b = _redis_client.get(key)
            if b:
                import pickle
                return pickle.loads(b)
            emb = _encode_cached(text)
            if emb is not None:
                try:
                    import pickle
                    _redis_client.set(key, pickle.dumps(emb), ex=60*60*24)
                except Exception:
                    pass
            return emb
        except Exception:
            pass
    # Fallback to in-memory cached encoder
    return _encode_cached(text)


_NEGATION_RE = re.compile(r"\b(not|no|never|n't|without|doesn't|don't|isn't|wasn't|cannot|can't|neither|nor)\b", flags=re.I)


def _has_negation(s: str) -> bool:
    if not s:
        return False
    return bool(_NEGATION_RE.search(s))


@dataclass
class Claim:
    id: str
    text: str
    sources: List[Dict[str, Any]]

    def corroboration_count(self) -> int:
        # Count distinct source URLs or titles
        seen = set()
        for s in self.sources:
            key = (s.get('url') or s.get('title') or '').strip().lower()
            if not key:
                key = repr(s)
            seen.add(key)
        return len(seen)


def label_claim_confidence(claim: Claim, high_threshold: int = 2) -> str:
    """Return a confidence label given the number of independent sources.

    - 'high' when corroboration_count >= high_threshold
    - 'medium' when corroboration_count == 1
    - 'low' when no sources
    """
    c = claim.corroboration_count()
    if c >= high_threshold:
        return 'high'
    if c == 1:
        return 'medium'
    return 'low'


def merge_claims(claims: List[Claim], min_sources_for_high: int = 2) -> List[Dict[str, Any]]:
    """Merge claims with identical text (simple normalization) and compute labels.

    Returns a list of dicts: {text, sources, corroboration, label}
    """
    # If no claims, return empty
    if not claims:
        return []

    # Build list of texts
    texts = [ (i, (c.text or '').strip()) for i, c in enumerate(claims) ]

    clusters: List[List[int]] = []

    def _similar(a: str, b: str) -> bool:
        if not a or not b:
            return False
        # Negation-aware check: if one has negation and the other doesn't, consider them different
        if _has_negation(a) != _has_negation(b):
            return False
        # Prefer semantic embeddings when available and cached
        try:
            emb_a = _get_embedding(a)
            emb_b = _get_embedding(b)
            if emb_a is not None and emb_b is not None and _np is not None and _norm is not None:
                v0, v1 = _np.array(emb_a), _np.array(emb_b)
                cos = float((v0 @ v1) / (_norm(v0) * _norm(v1) + 1e-12))
                return cos >= 0.88
        except Exception:
            # if anything goes wrong, continue to difflib
            pass
        # Fallback: difflib sequence matcher
        try:
            ratio = _difflib.SequenceMatcher(a=a.lower(), b=b.lower()).ratio()
            return ratio >= 0.85
        except Exception:
            return a.lower() == b.lower()

    for idx, txt in texts:
        placed = False
        for cl in clusters:
            # compare with first member in cluster
            if _similar(txt, texts[cl[0]][1]):
                cl.append(idx)
                placed = True
                break
        if not placed:
            clusters.append([idx])

    out = []
    for cl in clusters:
        merged_sources = []
        representative = None
        for i in cl:
            c = claims[i]
            if representative is None:
                representative = c.text
            merged_sources.extend(c.sources)
        merged_claim = Claim(id=str(cl[0]), text=representative or '', sources=merged_sources)
        label = label_claim_confidence(merged_claim, high_threshold=min_sources_for_high)
        out.append({
            'text': merged_claim.text,
            'sources': merged_claim.sources,
            'corroboration': merged_claim.corroboration_count(),
            'label': label,
        })
    return out
