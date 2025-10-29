import pytest
import types

from myai._llm_manager_impl import LLMManager, LLMError, call_llm_with_retries


class DummyManager(LLMManager):
    def __init__(self):
        super().__init__()
        self._call_count = 0
        self._responses = []

    def set_responses(self, responses):
        """Responses is a list where each item is either:
        - a dict to return from get_completion
        - an Exception to raise
        """
        self._responses = list(responses)

    def get_completion(self, messages, **kwargs):
        self._call_count += 1
        if not self._responses:
            return {"choices": [{"message": {"content": "default"}}]}
        r = self._responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get_streaming_completion(self, messages, **kwargs):
        # For tests that need streaming, return an iterator of chunks
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, list):
            for c in item:
                yield c
        else:
            yield item


def make_choice(text):
    return {"choices": [{"message": {"content": text}}]}


def test_happy_path_returns_text():
    m = DummyManager()
    m.set_responses([make_choice("Hello world")])
    out = call_llm_with_retries(m, messages=[{"role": "user", "content": "x"}], retries=1)
    assert out == "Hello world"


def test_transient_5xx_then_success():
    m = DummyManager()

    class TransientError(Exception):
        status_code = 502

    m.set_responses([TransientError("bad gateway"), make_choice("Recovered")])
    out = call_llm_with_retries(m, messages=[{"role": "user", "content": "x"}], retries=2, backoff_factor=0)
    assert out == "Recovered"


def test_persistent_5xx_raises_llmerror_and_writes_partial(tmp_path, monkeypatch):
    m = DummyManager()

    class ServerError(Exception):
        status_code = 500

    m.set_responses([ServerError("boom")])
    monkeypatch.setenv('MYAI_PARTIAL_DIR', str(tmp_path))
    with pytest.raises(LLMError) as ei:
        call_llm_with_retries(m, messages=[{"role": "user", "content": "x"}], retries=0, backoff_factor=0)
    e = ei.value
    assert e.code == '5xx'
    # ensure a partial file was written (may be empty)
    files = list(tmp_path.iterdir())
    assert any(p.name.startswith('partial_llm_') for p in files)


def test_4xx_immediate_llmerror():
    m = DummyManager()

    class ClientError(Exception):
        status_code = 400

    m.set_responses([ClientError("bad request")])
    with pytest.raises(LLMError) as ei:
        call_llm_with_retries(m, messages=[{"role": "user", "content": "x"}], retries=2, backoff_factor=0)
    e = ei.value
    assert e.code == '400'
