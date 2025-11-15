from myai import ethics

SAFE_ENV_VARS = [
    "LITELLM_BASE_URL",
    "EXA_URL",
    "LANGGRAPH_URL",
    "RAMALAMA_HOST",
    "TORM_URL",
]


def _clear_env(monkeypatch):
    for var in SAFE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_validate_resource_sources_pass(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("EXA_URL", "https://api.exa.ai/search")
    ok, issues = ethics.validate_resource_sources()
    assert ok
    assert issues == []


def test_validate_resource_sources_detects_bad_host(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("EXA_URL", "https://unvetted.example.org/search")
    ok, issues = ethics.validate_resource_sources()
    assert not ok
    assert any("unvetted.example.org" in issue for issue in issues)