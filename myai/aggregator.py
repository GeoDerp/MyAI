"""Simple aggregator to run research per perspective and merge results."""
from __future__ import annotations

from typing import List, Dict, Any
from dataclasses import dataclass
import logging

from .integrations import torm_expand_question
from ._research_agent import research_question_sync, ResearchSource, FinalAnswer
from .claims import Claim, merge_claims

logger = logging.getLogger(__name__)


@dataclass
class AggregatedResult:
    perspectives: List[Dict[str, Any]]
    answers: List[FinalAnswer]
    merged_sources: List[ResearchSource]
    claims: List[Dict[str, Any]]


def dedupe_sources(sources: List[ResearchSource]) -> List[ResearchSource]:
    seen = set()
    out = []
    for s in sources:
        key = (s.url or '').strip().lower() or (s.title or '').strip().lower()
        if not key:
            key = str(len(out))
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def aggregate_question(question: str, max_iterations: int = 6, min_confidence: int = 8) -> AggregatedResult:
    # Expand perspectives
    resp = torm_expand_question(question)
    perspectives = resp.get('perspectives') if isinstance(resp, dict) and 'perspectives' in resp else [{'id': 'core', 'text': question}]

    answers = []
    all_sources: List[ResearchSource] = []
    for p in perspectives:
        text = p.get('text') if isinstance(p, dict) else str(p)
        logger.info('Running research for perspective: %s', text)
        try:
            ans = research_question_sync(text, max_iterations=max_iterations, min_confidence=min_confidence)
            answers.append(ans)
            all_sources.extend(ans.evidence or [])
        except Exception:
            logger.exception('Perspective research failed; continuing')
            continue

    merged = dedupe_sources(all_sources)

    # Build simple claim objects from answers. For now we treat each FinalAnswer
    # as a single claim and associate its evidence. Convert ResearchSource
    # objects into lightweight dicts for merging and labeling.
    claim_objs: List[Claim] = []
    for i, ans in enumerate(answers):
        text = getattr(ans, 'answer', '') if ans is not None else ''
        srcs = []
        try:
            for s in getattr(ans, 'evidence', []) or []:
                # s may be a pydantic model; normalize to dict
                try:
                    srcs.append({'title': getattr(s, 'title', None), 'url': getattr(s, 'url', None)})
                except Exception:
                    srcs.append({'title': s.get('title') if isinstance(s, dict) else None, 'url': s.get('url') if isinstance(s, dict) else None})
        except Exception:
            srcs = []
        claim_objs.append(Claim(id=str(i), text=(text or '').strip(), sources=srcs))

    merged_claims = merge_claims(claim_objs, min_sources_for_high=2)

    return AggregatedResult(perspectives=perspectives, answers=answers, merged_sources=merged, claims=merged_claims)
