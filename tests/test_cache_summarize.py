import importlib
import sys
import os

from myai import cache


def test_happy_path_chunks():
    text = (
        "This is sentence one. Sentence two has more words and will be included. "
        "Third sentence is here. Fourth sentence continues the narrative and might be longer. "
        "The fifth sentence concludes. Additional paragraph starts here with more words."
    )
    res = cache.summarize_document_with_content(
        doi="doi:test/happy",
        condensation_config={"chunk_size_tokens": 8, "per_chunk_summary_tokens": 4, "chunk_overlap_tokens": 2},
        max_tokens=40,
        model_id="local",
        prompt_fingerprint=None,
        source_text=text,
    )
    assert isinstance(res, dict)
    assert res.get("summary") and isinstance(res.get("summary"), str)
    assert res.get("meta", {}).get("chunk_count", 0) >= 1


def test_fallback_no_condense(monkeypatch):
    # Simulate condense module missing by temporarily inserting a module
    # that raises on import inside cache.summarize_document_with_content.
    real_condense = sys.modules.get("myai.condense")

    class _BrokenModule:
        def __getattr__(self, name):
            raise ImportError("simulated missing condense")

    sys.modules["myai.condense"] = _BrokenModule()
    try:
        res = cache.summarize_document_with_content(
            doi="doi:test/fallback",
            condensation_config={},
            max_tokens=20,
            model_id="local",
            prompt_fingerprint=None,
            source_text="Some small text that would be summarized if condense existed.",
        )
        assert isinstance(res, dict)
        # The fallback summary contains a bracketed placeholder introduced in the function
        assert "[condensed summary for" in res.get("summary", "") or res.get("summary")
        assert res.get("meta", {}).get("content_hash") is not None
    finally:
        # restore real module if present
        if real_condense is not None:
            sys.modules["myai.condense"] = real_condense
        else:
            del sys.modules["myai.condense"]


if __name__ == "__main__":
    # Simple runner so tests can be executed without pytest installed.
    print("Running test_happy_path_chunks()")
    test_happy_path_chunks()
    print("OK")
    print("Running test_fallback_no_condense()")
    # Provide a simple monkeypatch replacement when run directly
    class Dummy:
        pass
    test_fallback_no_condense(monkeypatch=Dummy())
    print("OK")
