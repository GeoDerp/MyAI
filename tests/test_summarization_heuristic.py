import os
import importlib

import pytest

from myai._research_agent import should_enable_summarization


def test_explicit_override_true():
    enabled, reason = should_enable_summarization(None, True)
    assert enabled is True
    assert reason == "explicit override"


def test_explicit_override_false():
    enabled, reason = should_enable_summarization('openai:gpt-4o', False)
    assert enabled is False
    assert reason == "explicit override"


def test_http_endpoint_enables():
    enabled, reason = should_enable_summarization('http://localhost:8080/v1', None)
    assert enabled is True
    assert 'local_endpoint' in reason


def test_local_model_name_enables():
    enabled, reason = should_enable_summarization('gpt-oss:20b', None)
    assert enabled is True
    assert 'local_model_name' in reason


def test_no_local_indicators_disables(tmp_path, monkeypatch):
    # Ensure no RAMALAMA env vars
    monkeypatch.delenv('RAMALAMA_HOST', raising=False)
    monkeypatch.delenv('RAMALAMA_PORT', raising=False)
    enabled, reason = should_enable_summarization('openai:gpt-4o', None)
    assert enabled is False
    assert reason.startswith('heuristic:') and 'no_local_indicators' in reason
