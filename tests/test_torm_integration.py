from myai.integrations import torm_expand_question


def test_torm_fallback_no_env(monkeypatch):
    monkeypatch.delenv('TORM_URL', raising=False)
    out = torm_expand_question('Is X safe?')
    assert 'perspectives' in out
    assert len(out['perspectives']) >= 1
