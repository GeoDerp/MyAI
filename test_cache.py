import os
import shutil
import json
from myai import cache


def test_cache_set_and_get(tmp_path):
    # Use a temporary cache dir by monkeypatching CACHE_DIR via environment
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        # Create cache dir implicitly
        key = cache.make_fingerprint("10.1000/testdoc", "cfg")
        value = {"doi": "10.1000/testdoc", "summary": "hello"}
        cache.cache_set(key, value)
        loaded = cache.cache_get(key)
        assert loaded is not None
        assert loaded["doi"] == "10.1000/testdoc"
    finally:
        os.chdir(orig_cwd)


def test_summarize_document_creates_cache(tmp_path):
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cfg = {"method": "extractive"}
        out = cache.summarize_document("10.1000/testdoc", cfg, max_tokens=100)
        assert "fingerprint" in out
        # Re-call should load from cache and return same fingerprint
        out2 = cache.summarize_document("10.1000/testdoc", cfg, max_tokens=100)
        assert out2.get("fingerprint") == out.get("fingerprint")
    finally:
        os.chdir(orig_cwd)


def test_cache_invalidate_and_fingerprint(tmp_path):
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        cfg = {"method": "extractive"}
        out = cache.summarize_document_with_content("10.1000/testdoc", cfg, max_tokens=50, model_id="m1", prompt_fingerprint="p1", source_text="hello world")
        fp = out.get("fingerprint")
        assert fp
        assert cache.cache_exists(fp)
        # Invalidate
        assert cache.cache_invalidate(fp) is True
        assert cache.cache_get(fp) is None
    finally:
        os.chdir(orig_cwd)


def test_extractive_summarize_reduces_tokens():
    from myai.condense import extractive_summarize, estimate_tokens

    text = (
        "This is sentence one. "
        "This is sentence two which is longer and contains more words to consume tokens. "
        "This is sentence three. "
        "This is sentence four with additional content to test summarization."
    )
    orig_tokens = estimate_tokens(text)
    summary, meta = extractive_summarize(text, max_tokens=max(1, orig_tokens // 2))
    assert isinstance(summary, str)
    assert meta["tokens"] <= orig_tokens
