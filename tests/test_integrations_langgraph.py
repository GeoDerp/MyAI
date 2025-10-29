import os

from myai.integrations import langgraph_client
from myai.provenance import write_provenance_bundle


def test_langgraph_client_none_by_default(monkeypatch):
    monkeypatch.delenv('LANGGRAPH_URL', raising=False)
    client = langgraph_client()
    assert client is None


def test_write_provenance_bundle_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv('MYAI_PARTIAL_DIR', str(tmp_path))
    sources = [
        {'title': 'A', 'url': 'http://example.com', 'confidence': 5},
        {'title': 'B', 'url': None, 'confidence': 4},
    ]
    path = write_provenance_bundle(sources, metadata={'q': 'x'})
    assert path
    assert os.path.exists(path)
    # ensure file content is JSON and contains our sources
    import json
    with open(path, 'r') as fh:
        obj = json.load(fh)
    assert 'sources' in obj and len(obj['sources']) == 2
