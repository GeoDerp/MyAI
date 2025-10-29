"""Provenance helpers for writing provenance bundles to disk.

This module provides a simple file-based fallback for persisting sources and
writing a bundle when LangGraph is not configured or reachable.
"""
from __future__ import annotations

import json
import os
import datetime
from typing import List, Dict, Any


def write_provenance_bundle(sources: List[Dict[str, Any]], metadata: Dict[str, Any] | None = None, outdir: str | None = None) -> str:
    """Write a provenance bundle JSON to MYAI_PARTIAL_DIR (or provided outdir) and return the path.

    The bundle contains the provided sources plus optional run metadata. This
    is best-effort: failures return an empty string.
    """
    outdir = outdir or os.environ.get('MYAI_PARTIAL_DIR', '/tmp')
    # Ensure outdir exists
    try:
        os.makedirs(outdir, exist_ok=True)
    except Exception:
        pass
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    fname = os.path.join(outdir, f'provenance_bundle_{ts}.json')
    bundle = {
        'created_at': ts,
        'sources': sources,
        'metadata': metadata or {},
    }
    try:
        with open(fname, 'w') as fh:
            json.dump(bundle, fh, indent=2)
    except Exception:
        # Best-effort; don't raise to avoid breaking research flows
        return ''
    return fname
