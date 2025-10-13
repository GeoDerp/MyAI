"""
Lightweight condensation utilities: token estimation and a simple
extractive summarizer that picks sentences until a token budget is hit.

This is intentionally small and dependency-free so it can be used in tests
and in minimal production environments without heavy ML dependencies.
"""
from __future__ import annotations

import re
from typing import List, Tuple


def split_sentences(text: str) -> List[str]:
    # naive sentence splitter
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def estimate_tokens(text: str) -> int:
    """Rudimentary token estimator: uses word count scaled down to approximate tokens.

    This is not exact but is sufficient for budgeting in the condensation step.
    """
    if not text:
        return 0
    words = text.split()
    # Approximate tokens ~= words * 0.75 (very rough)
    return max(1, int(len(words) * 0.75))


def extractive_summarize(text: str, max_tokens: int) -> Tuple[str, dict]:
    """Extractive summarizer: select sentences in document order until
    token budget is satisfied.

    Returns (summary_text, meta) where meta contains which sentence indices were used
    and token counts.
    """
    sentences = split_sentences(text)
    if not sentences:
        return "", {"chunks": 0, "tokens": 0}

    selected = []
    total_tokens = 0
    used_indices = []
    for i, s in enumerate(sentences):
        t = estimate_tokens(s)
        if total_tokens + t > max_tokens:
            break
        selected.append(s)
        used_indices.append(i)
        total_tokens += t

    if not selected:
        # take first sentence as fallback
        selected = [sentences[0]]
        used_indices = [0]
        total_tokens = estimate_tokens(sentences[0])

    summary = " ".join(selected)
    meta = {"chunks": len(selected), "tokens": total_tokens, "indices": used_indices}
    return summary, meta
