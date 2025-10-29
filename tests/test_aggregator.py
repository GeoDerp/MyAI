from myai import aggregator
from myai._research_agent import FinalAnswer, ResearchSource


def make_final(answer_text, sources):
    f = FinalAnswer(answer=answer_text, confidence=5.0, reasoning='r')
    f.evidence = sources
    return f


def test_aggregate_dedupes(monkeypatch):
    # Create two perspectives that will return overlapping sources
    s1 = ResearchSource(title='A', url='http://example.com', confidence=5)
    s2 = ResearchSource(title='B', url='http://example.org', confidence=4)
    s3 = ResearchSource(title='A duplicate', url='http://example.com', confidence=3)

    def fake_research(q, max_iterations=6, min_confidence=8):
        # return different answers depending on query
        if 'Technical' in q:
            return make_final('tech', [s1, s2])
        return make_final('core', [s3])

    monkeypatch.setattr(aggregator, 'research_question_sync', fake_research)
    res = aggregator.aggregate_question('Q', max_iterations=1, min_confidence=1)
    # merged_sources should dedupe by URL and have 2 unique urls
    assert len(res.merged_sources) == 2
