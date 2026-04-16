from unittest.mock import MagicMock
import services.web_search_service as web_search_module


def test_returns_formatted_results(mock_tavily):
    """Mock Tavily returns 2 results + answer; output contains title, URL, and summary."""
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "answer": "Python is a programming language.",
        "results": [
            {"title": "Python Docs", "url": "https://docs.python.org", "content": "Python is great."},
            {"title": "Real Python", "url": "https://realpython.com", "content": "Learn Python here."},
        ],
    }
    mock_tavily.return_value = mock_client

    result = web_search_module.web_search("What is Python?")

    assert "Python Docs" in result
    assert "https://docs.python.org" in result
    assert "Python is a programming language." in result


def test_empty_results_message(mock_tavily):
    """Mock Tavily returns empty results list; returns 'No results found.'"""
    mock_client = MagicMock()
    mock_client.search.return_value = {"results": []}
    mock_tavily.return_value = mock_client

    result = web_search_module.web_search("unknown query")

    assert result == "No results found."


def test_includes_tavily_answer_when_present(mock_tavily):
    """include_answer=True passed to search; summary section appears in output."""
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "answer": "The synthesized answer.",
        "results": [{"title": "Source", "url": "https://example.com", "content": "Some content."}],
    }
    mock_tavily.return_value = mock_client

    result = web_search_module.web_search("some question")

    assert "The synthesized answer." in result
    mock_client.search.assert_called_once_with("some question", max_results=5, include_answer=True)


def test_exception_returns_error_string(mock_tavily):
    """TavilyClient raises; result is error string, no propagation."""
    mock_tavily.side_effect = Exception("API key invalid")

    result = web_search_module.web_search("query")

    assert result.startswith("[web_search error:")


def test_content_truncated_at_400_chars(mock_tavily):
    """Result content of 1000 chars is truncated to 400 in output."""
    long_content = "x" * 1000
    mock_client = MagicMock()
    mock_client.search.return_value = {
        "results": [{"title": "Title", "url": "https://example.com", "content": long_content}],
    }
    mock_tavily.return_value = mock_client

    result = web_search_module.web_search("query")

    assert "x" * 401 not in result
    assert "x" * 400 in result
