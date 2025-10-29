"""Integration adapters: LangGraph, TORM, Exa stubs.

These are lightweight, opt-in adapters. If corresponding env vars are not
set the adapters fall back to no-op behaviour to keep the core code simple.
"""
from __future__ import annotations

import os
import uuid
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class LangGraphClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    def create_source(self, source: Dict[str, Any]) -> str:
        """Create a source node in LangGraph. Returns a stable id on success.

        The default implementation does a best-effort HTTP POST if a URL is
        configured. For simple local testing we fall back to returning a
        deterministic UUID based on the URL/title to allow idempotency.
        """
        try:
            import requests

            url = f"{self.base_url}/sources"
            resp = requests.post(url, json=source, timeout=5)
            if resp.status_code >= 200 and resp.status_code < 300:
                data = resp.json()
                return data.get('id') or data.get('source_id') or str(uuid.uuid4())
            logger.debug('LangGraph create_source returned status %s', resp.status_code)
        except Exception:
            # Fall back to deterministic uuid5 based on URL/title
            try:
                name = (source.get('url') or source.get('title') or '')
                ns = uuid.NAMESPACE_URL
                return str(uuid.uuid5(ns, name or str(source)))
            except Exception:
                return str(uuid.uuid4())

    def bulk_create_sources(self, sources: List[Dict[str, Any]]) -> List[str]:
        return [self.create_source(s) for s in sources]


def langgraph_client() -> Optional[LangGraphClient]:
    """Return a LangGraphClient if LANGGRAPH_URL is set, else None.

    This design makes LangGraph opt-in: call sites can check for None and
    fall back to file-based persistence when the adapter is not present.
    """
    base = os.environ.get('LANGGRAPH_URL')
    if not base:
        return None
    return LangGraphClient(base)


def torm_expand_question(question: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Expand a question into perspectives. Returns a simple fallback when TORM is not configured."""
    url = base_url or os.environ.get('TORM_URL')
    if url:
        try:
            import requests
            resp = requests.post(f"{url.rstrip('/')}/expand", json={'question': question}, timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            logger.debug('TORM expand request failed; falling back')
    perspectives = [
        {'id': 'core', 'text': question},
        {'id': 'technical', 'text': f"Technical perspective: {question}"},
        {'id': 'policy', 'text': f"Policy/ethical perspective: {question}"},
    ]
    return {'perspectives': perspectives}


def ramalama_model_url(host: Optional[str] = None, port: Optional[int] = None) -> str:
    host = host or os.environ.get('RAMALAMA_HOST', 'localhost')
    port = port or int(os.environ.get('RAMALAMA_PORT', '8080'))
    return f'http://{host}:{port}/v1'


def exa_search(query: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """Stub for Exa search adapter. Returns an empty list if EXA not configured."""
    key = api_key or os.environ.get('EXA_API_KEY')
    if not key:
        return []
    try:
        import requests
        url = os.environ.get('EXA_URL') or 'https://api.exa.example/search'
        resp = requests.get(url, params={'q': query, 'key': key}, timeout=5)
        if resp.status_code == 200:
            items = resp.json().get('results', [])
            normalized = []
            for it in items:
                normalized.append({
                    'title': it.get('title') or it.get('heading'),
                    'URL': it.get('url'),
                    'raw': {'text': it.get('snippet') or it.get('excerpt')},
                })
            return normalized
    except Exception:
        logger.debug('Exa search failed')
    return []


__all__ = ['langgraph_client', 'torm_expand_question', 'ramalama_model_url', 'exa_search']
