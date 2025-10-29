"""
Minimal Academic Retrieval Agent utilities.

This module provides lightweight utilities to search academic metadata
and resolve DOIs/PMIDs. It's intentionally small and network-calls are
performed via the requests library so tests can easily mock requests.

Functions provided:
- search_academic(topic, max_results=5): returns list of candidate records
- resolve_doi(doi): returns CrossRef-like metadata for a DOI (if reachable)

This is the first incremental implementation requested in README.md's TODO
— it focuses on structured metadata retrieval and provenance (DOI/PMID).
"""
from __future__ import annotations

from typing import List, Optional, Dict, Any
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - fallback for environments without requests
    # Provide a minimal requests-like shim using urllib so tests and code
    # that patch `myai.academic_retrieval.requests.get` still work.
    import urllib.request
    import urllib.parse
    import json as _json

    class _ShimResponse:
        def __init__(self, body: bytes, status: int = 200):
            self._body = body
            self.status_code = status

        def json(self):
            return _json.loads(self._body.decode("utf-8"))

        def raise_for_status(self):
            if 400 <= self.status_code:
                raise Exception(f"HTTP error: {self.status_code}")

    class _RequestsShim:
        @staticmethod
        def get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 10):
            if params:
                sep = '&' if '?' in url else '?'
                url = url + sep + urllib.parse.urlencode(params)
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read()
                return _ShimResponse(body, status=resp.getcode())

    requests = _RequestsShim()
import logging

logger = logging.getLogger(__name__)

DEFAULT_CROSSREF_URL = "https://api.crossref.org/works"


def _safe_get_json(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Optional[Dict[str, Any]]:
    try:
        resp = requests.get(url, params=params or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("Network call failed for %s: %s", url, e)
        return None


def resolve_doi(doi: str, crossref_base: str = DEFAULT_CROSSREF_URL) -> Optional[Dict[str, Any]]:
    """Resolve a DOI to basic metadata using CrossRef.

    Returns a dict with keys like 'title', 'abstract', 'DOI', 'URL', 'issued',
    'publisher', and 'type' when available. Returns None on network/error.
    """
    if not doi:
        return None
    # CrossRef expects encoded DOIs as path suffix
    url = f"{crossref_base}/{doi}"
    data = _safe_get_json(url)
    if not data:
        return None
    # CrossRef wraps actual metadata under 'message'
    msg = data.get("message") if isinstance(data, dict) else None
    if not msg:
        return None
    # Normalize a minimal subset
    out = {
        "title": (msg.get("title") or [None])[0],
        "DOI": msg.get("DOI"),
        "URL": msg.get("URL"),
        "publisher": msg.get("publisher"),
        "issued": msg.get("issued"),
        "type": msg.get("type"),
        "abstract": msg.get("abstract"),
    }
    return out


def search_academic(topic: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Perform a very small academic search by querying CrossRef's works endpoint.

    This is deliberately conservative: CrossRef supports text queries and
    returns structured metadata. We return a list of candidate records that
    include DOI when available.

    Note: This function is network-dependent; unit tests should mock
    requests.get to simulate realistic responses.
    """
    if not topic:
        return []
    params = {
        "query.title": topic,
        "rows": max_results,
    }
    data = _safe_get_json(DEFAULT_CROSSREF_URL, params=params)
    if not data:
        return []
    items = data.get("message", {}).get("items", [])
    results: List[Dict[str, Any]] = []
    for it in items:
        results.append({
            "title": (it.get("title") or [None])[0],
            "DOI": it.get("DOI"),
            "URL": it.get("URL"),
            "publisher": it.get("publisher"),
            "issued": it.get("issued"),
            "type": it.get("type"),
            "is_oa": bool(it.get("license")),
            "raw": it,
        })
    return results


def filter_candidates(
    candidates: List[Dict[str, Any]],
    prefer_peer_review: bool = True,
    min_year: Optional[int] = None,
    prefer_oa: bool = True,
) -> List[Dict[str, Any]]:
    """Apply quality filters to candidates and return a ranked list.

    - prefer_peer_review: try to prioritize items likely to be peer-reviewed (heuristic)
    - min_year: filter out items older than this year (e.g., 2019)
    - prefer_oa: boost open-access items
    """
    if not candidates:
        return []

    def is_peer_reviewed(c: Dict[str, Any]) -> bool:
        # Heuristic: many CrossRef items include 'type' or 'container-title' for journals
        t = c.get("type") or ""
        if "journal" in (t or ""):
            return True
        raw = c.get("raw") or {}
        # Some items include 'container-title' (journal) or 'journal-title'
        if raw:
            if raw.get("container-title") or raw.get("journal-title"):
                return True
        return False

    def year_of(c: Dict[str, Any]) -> Optional[int]:
        issued = c.get("issued")
        if isinstance(issued, dict):
            dp = issued.get("date-parts")
            if dp and isinstance(dp, list) and dp[0]:
                return dp[0][0]
        return None

    filtered = []
    for c in candidates:
        y = year_of(c)
        if min_year and y is not None and y < min_year:
            continue
        score = 0
        if prefer_oa and c.get("is_oa"):
            score += 10
        if c.get("DOI"):
            score += 5
        if is_peer_reviewed(c):
            score += 8
        if y:
            score += min(max(y - 2000, 0), 20)
        filtered.append((score, c))

    filtered.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in filtered]


def search_with_fallback(
    topic: str,
    max_results: int = 5,
    min_year: Optional[int] = None,
    prefer_peer_review: bool = True,
    prefer_oa: bool = True,
    fallback_fn=None,
) -> List[Dict[str, Any]]:
    """Search academic sources first (CrossRef). If insufficient high-quality
    results are found, call fallback_fn(topic) and return its results.

    fallback_fn should be a callable that accepts (topic) and returns a list
    of candidate dicts or a textual result.
    """
    candidates = search_academic(topic, max_results=max_results)
    ranked = filter_candidates(candidates, prefer_peer_review=prefer_peer_review, min_year=min_year, prefer_oa=prefer_oa)
    # If we have at least one result that looks peer-reviewed, return it
    if ranked:
        # If prefer_peer_review is True, ensure at least one peer-reviewed item
        if not prefer_peer_review:
            return ranked
        for c in ranked:
            # heuristically decide peer-review
            t = c.get("type") or ""
            if "journal" in t or c.get("DOI"):
                return ranked
    # Otherwise fallback: prefer caller-provided fallback_fn; if not present
    # try Exa adapter when configured; otherwise call fallback_fn if provided.
    if fallback_fn is not None:
        try:
            return fallback_fn(topic)
        except Exception:
            return []

    # If no fallback_fn was provided, attempt to use the optional Exa adapter
    try:
        from myai.integrations import exa_search
        exa_results = exa_search(topic)
        if exa_results:
            # Normalize Exa results into candidate dicts similar to CrossRef
            normalized = []
            for it in exa_results:
                normalized.append({
                    'title': it.get('title'),
                    'DOI': None,
                    'URL': it.get('URL') or it.get('url'),
                    'publisher': None,
                    'issued': None,
                    'type': 'web',
                    'is_oa': True,
                    'raw': it,
                })
            return normalized
    except Exception:
        logger.debug('Exa adapter not available or failed')

    return []
    return []


def pick_best_candidates(candidates: List[Dict[str, Any]], prefer_oa: bool = True) -> List[Dict[str, Any]]:
    """Rank and filter candidates. Currently a simple heuristic:
    - Prefer open-access (license present) when prefer_oa True
    - Then prefer presence of DOI
    - Then return up to len(candidates) results in ranked order
    """
    if not candidates:
        return []
    def score(c: Dict[str, Any]) -> int:
        s = 0
        if c.get("is_oa"):
            s += 10
        if c.get("DOI"):
            s += 5
        # Prefer newer works if issued.year exists
        issued = c.get("issued")
        year = None
        if isinstance(issued, dict):
            # CrossRef has issued:{'date-parts': [[YYYY,MM,DD]]}
            dp = issued.get("date-parts")
            if dp and isinstance(dp, list) and dp[0]:
                year = dp[0][0]
        if isinstance(year, int):
            s += min(max(year - 2000, 0), 20)
        return s

    ranked = sorted(candidates, key=score, reverse=True)
    if prefer_oa:
        # move OA to front (already scored) — return full ranked list
        return ranked
    return ranked
