"""
Tests for the lightweight summarizer in the research agent
Run with: pytest -q
"""
from myai._research_agent import summarize_text, ResearchDependencies


def test_summarize_truncates_to_sentences():
    long_text = """
    This is sentence one. This is sentence two which is a bit longer. Here is sentence three.
    """

    out = summarize_text(long_text, max_chars=50)
    assert out.endswith('... [summary]') or len(out) <= 50


def test_deps_flag_default_false():
    deps = ResearchDependencies()
    assert deps.enable_summarization is False


def test_deps_flag_can_be_set():
    deps = ResearchDependencies()
    deps.enable_summarization = True
    assert deps.enable_summarization is True
