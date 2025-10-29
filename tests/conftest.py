import pytest
import os
from unittest.mock import Mock, MagicMock


@pytest.fixture(autouse=True)
def set_partial_dir(tmp_path, monkeypatch):
    """Ensure tests write partial/provenance files to the test tmpdir by default."""
    monkeypatch.setenv('MYAI_PARTIAL_DIR', str(tmp_path))
    monkeypatch.setenv('MYAI_RENDERED_OUTPUT', str(tmp_path / 'research_report.html'))
    yield


@pytest.fixture
def mock_llm_server():
    """Mock LLM server that returns predefined responses."""
    mock = Mock()
    mock.call_count = 0
    mock.responses = []
    
    def get_completion(messages, **kwargs):
        mock.call_count += 1
        if mock.responses:
            response = mock.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return {'choices': [{'message': {'content': 'Mock response'}}]}
    
    mock.get_completion = get_completion
    return mock


@pytest.fixture
def mock_retrieval_service():
    """Mock retrieval service for web/academic search."""
    mock = Mock()
    mock.search_results = [
        {
            'title': 'Test Article 1',
            'url': 'https://example.com/1',
            'snippet': 'This is a test article about X.',
            'confidence': 0.8
        },
        {
            'title': 'Test Article 2',
            'url': 'https://example.com/2',
            'snippet': 'More information about X.',
            'confidence': 0.7
        }
    ]
    
    def search(query, **kwargs):
        return mock.search_results
    
    mock.search = search
    return mock


@pytest.fixture
def mock_langgraph_client():
    """Mock LangGraph client for provenance storage."""
    mock = Mock()
    mock.sources_created = []
    
    def create_source(source):
        mock.sources_created.append(source)
        return f"source-{len(mock.sources_created)}"
    
    mock.create_source = create_source
    return mock


@pytest.fixture
def disable_external_calls(monkeypatch):
    """Disable all external network calls in tests."""
    def no_requests(*args, **kwargs):
        raise RuntimeError("External network calls disabled in tests")
    
    try:
        import requests
        monkeypatch.setattr(requests, 'get', no_requests)
        monkeypatch.setattr(requests, 'post', no_requests)
    except ImportError:
        pass
    
    yield
