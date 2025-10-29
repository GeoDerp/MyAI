import os
import json
from unittest.mock import patch

import pytest

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

webui_path = Path(__file__).resolve().parents[1] / 'webui.py'
spec = importlib.util.spec_from_loader('webui', importlib.machinery.SourceFileLoader('webui', str(webui_path)))
webui = importlib.util.module_from_spec(spec)
sys.modules['webui'] = webui
spec.loader.exec_module(webui)
flask_app = webui.app


@pytest.mark.usefixtures('set_partial_dir')
def test_webui_post_writes_html_and_provenance(monkeypatch, tmp_path):
    # Patch the research endpoint to return a simple result with provenance
    fake_result = {
        'report': 'Research Results',
        'provenance': {'by_fingerprint': {'fp1': {'title': 'A', 'url': 'http://a'}}},
    }

    async def fake_test_research_endpoint(topic, base_url=None):
        return fake_result

    monkeypatch.setenv('MYAI_RENDERED_OUTPUT', str(tmp_path / 'report.html'))
    monkeypatch.setenv('MYAI_PARTIAL_DIR', str(tmp_path))

    with patch('webui.test_research_endpoint', new=fake_test_research_endpoint):
        client = flask_app.test_client()
        resp = client.post('/', data={'question': 'What is X?', 'max_iterations': '1'})
        assert resp.status_code == 200

    # Ensure rendered HTML file exists
    html_path = tmp_path / 'report.html'
    assert html_path.exists()

    # Check that a provenance bundle file was written to partial dir
    files = list(tmp_path.iterdir())
    assert any(p.name.startswith('provenance_bundle_') for p in files)
