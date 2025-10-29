from unittest.mock import patch

import myai.academic_retrieval as ar


def test_exa_used_when_no_crossref(monkeypatch):
    # Ensure CrossRef search returns empty
    monkeypatch.setattr(ar, 'search_academic', lambda topic, max_results=5: [])

    # Patch the integrations.exa_search to return sample items
    sample = [{'title': 'Exa result', 'url': 'http://exa.example/article', 'raw': {'snippet': 'x'}}]

    with patch('myai.integrations.exa_search', return_value=sample):
        res = ar.search_with_fallback('quantum', max_results=3)
    assert isinstance(res, list)
    assert res and res[0].get('title') == 'Exa result'
