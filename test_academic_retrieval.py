import json
from unittest.mock import patch, Mock

import myai.academic_retrieval as ar


def _fake_crossref_doi_response(doi: str):
    return {
        "status": "ok",
        "message-type": "work",
        "message-version": "1.0.0",
        "message": {
            "title": ["Example Paper Title"],
            "DOI": doi,
            "URL": f"https://doi.org/{doi}",
            "publisher": "Example Publisher",
            "issued": {"date-parts": [[2023, 1, 1]]},
            "type": "journal-article",
            "abstract": "<p>Abstract text</p>",
        }
    }


def _fake_crossref_search_response():
    return {
        "status": "ok",
        "message-type": "work-list",
        "message": {
            "items": [
                {
                    "title": ["Example Paper A"],
                    "DOI": "10.1000/examplea",
                    "URL": "https://doi.org/10.1000/examplea",
                    "publisher": "Example Pub A",
                    "issued": {"date-parts": [[2022]]},
                    "type": "journal-article",
                    "license": [{"URL": "https://open.example/license"}],
                },
                {
                    "title": ["Example Paper B"],
                    "DOI": "10.1000/exampleb",
                    "URL": "https://doi.org/10.1000/exampleb",
                    "publisher": "Example Pub B",
                    "issued": {"date-parts": [[2019]]},
                    "type": "journal-article",
                }
            ]
        }
    }


@patch("myai.academic_retrieval.requests.get")
def test_resolve_doi(mock_get):
    doi = "10.1000/example"
    fake = _fake_crossref_doi_response(doi)
    m = Mock()
    m.json.return_value = fake
    m.raise_for_status.return_value = None
    mock_get.return_value = m

    meta = ar.resolve_doi(doi)
    assert meta is not None
    assert meta.get("DOI") == doi
    assert "Example Paper" in (meta.get("title") or "")


@patch("myai.academic_retrieval.requests.get")
def test_search_academic_and_ranking(mock_get):
    fake = _fake_crossref_search_response()
    m = Mock()
    m.json.return_value = fake
    m.raise_for_status.return_value = None
    mock_get.return_value = m

    results = ar.search_academic("example topic", max_results=2)
    assert isinstance(results, list)
    assert len(results) == 2
    # Prefer OA first
    ranked = ar.pick_best_candidates(results, prefer_oa=True)
    assert ranked[0]["DOI"] == "10.1000/examplea"


def test_search_with_fallback_calls_fallback(monkeypatch):
    # Simulate search_academic returning empty list
    monkeypatch.setattr(ar, "search_academic", lambda topic, max_results=5: [])
    called = {"fallback": False}

    def fallback_fn(topic):
        called["fallback"] = True
        return [{"title": "fb", "DOI": None, "raw": {"text": "fallback text"}}]

    res = ar.search_with_fallback("topic", max_results=2, fallback_fn=fallback_fn)
    assert called["fallback"] is True
    assert isinstance(res, list)
    assert res[0]["title"] == "fb"
