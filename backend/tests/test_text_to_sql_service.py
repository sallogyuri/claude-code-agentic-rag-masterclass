from unittest.mock import MagicMock, patch
import services.text_to_sql_service as text_to_sql_module


def _make_mock_llm(sql: str):
    """Return a mock LLM client that responds with the given SQL string."""
    mock_llm = MagicMock()
    mock_llm.chat.completions.create.return_value.choices[0].message.content = sql
    return mock_llm


def _make_mock_conn(rows: list[dict]):
    """Return a mock psycopg2 connection that yields the given rows."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchmany.return_value = rows

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn


def test_generate_and_execute_returns_table_string(monkeypatch, mock_psycopg2_connect):
    """Mock LLM returns valid SQL, mock cursor returns 2 rows; output contains headers and values."""
    user_id = "test-user-123"
    sql = f"SELECT id, name FROM documents WHERE user_id = '{user_id}'"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))

    rows = [{"id": "abc", "name": "file.pdf"}, {"id": "def", "name": "doc.txt"}]
    mock_psycopg2_connect.return_value = _make_mock_conn(rows)

    returned_sql, result = text_to_sql_module.text_to_sql("How many documents?", user_id)

    assert returned_sql == sql
    assert "id" in result
    assert "name" in result
    assert "abc" in result
    assert "file.pdf" in result


def test_empty_result_returns_no_results_message(monkeypatch, mock_psycopg2_connect):
    """Mock cursor returns no rows; returns 'no results' message."""
    user_id = "test-user-123"
    sql = f"SELECT id FROM documents WHERE user_id = '{user_id}'"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))
    mock_psycopg2_connect.return_value = _make_mock_conn([])

    returned_sql, result = text_to_sql_module.text_to_sql("Any docs?", user_id)

    assert returned_sql == sql
    assert "no results" in result.lower()


def test_non_select_sql_returns_error_string(monkeypatch, mock_psycopg2_connect):
    """LLM returns DELETE statement; result starts with [text_to_sql error:."""
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm("DELETE FROM documents"))

    _, result = text_to_sql_module.text_to_sql("Delete everything", "test-user-123")

    assert result.startswith("[text_to_sql error:")


def test_forbidden_keyword_returns_error_string(monkeypatch, mock_psycopg2_connect):
    """LLM returns SELECT with DROP; result starts with [text_to_sql error:."""
    user_id = "test-user-123"
    sql = f"SELECT * FROM documents WHERE user_id = '{user_id}'; DROP TABLE documents"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))

    _, result = text_to_sql_module.text_to_sql("List docs", user_id)

    assert result.startswith("[text_to_sql error:")


def test_missing_user_id_returns_error_string(monkeypatch, mock_psycopg2_connect):
    """LLM returns SQL without user_id filter; result starts with [text_to_sql error:."""
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm("SELECT id, name FROM documents"))

    _, result = text_to_sql_module.text_to_sql("List all docs", "test-user-123")

    assert result.startswith("[text_to_sql error:")


def test_db_exception_returns_error_string(monkeypatch, mock_psycopg2_connect):
    """psycopg2.connect raises; result is error string, no propagation."""
    user_id = "test-user-123"
    sql = f"SELECT id FROM documents WHERE user_id = '{user_id}'"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))
    mock_psycopg2_connect.side_effect = Exception("Connection refused")

    _, result = text_to_sql_module.text_to_sql("List docs", user_id)

    assert result.startswith("[text_to_sql error:")


def test_llm_exception_returns_error_string(monkeypatch, mock_psycopg2_connect):
    """LLM call raises; result is error string, no propagation."""
    mock_llm = MagicMock()
    mock_llm.chat.completions.create.side_effect = Exception("LLM unavailable")
    monkeypatch.setattr(text_to_sql_module, "_llm", mock_llm)

    _, result = text_to_sql_module.text_to_sql("List docs", "test-user-123")

    assert result.startswith("[text_to_sql error:")


def test_sales_data_query_no_user_id_required(monkeypatch, mock_psycopg2_connect):
    """SQL against public table (sales_data) without user_id passes validation."""
    user_id = "test-user-123"
    sql = "SELECT region, SUM(total_amount) FROM sales_data GROUP BY region ORDER BY 2 DESC"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))

    rows = [{"region": "North America", "sum": 15000.0}, {"region": "Europe", "sum": 9500.0}]
    mock_psycopg2_connect.return_value = _make_mock_conn(rows)

    returned_sql, result = text_to_sql_module.text_to_sql("Total sales by region", user_id)

    assert returned_sql == sql
    assert "region" in result
    assert "North America" in result
    assert not result.startswith("[text_to_sql error:")


def test_markdown_fenced_sql_is_accepted(monkeypatch, mock_psycopg2_connect):
    """LLM wraps SQL in ```sql fences; fences must be stripped before validation."""
    user_id = "test-user-123"
    raw_sql = f"SELECT id, name FROM documents WHERE user_id = '{user_id}'"
    fenced_sql = f"```sql\n{raw_sql}\n```"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(fenced_sql))

    rows = [{"id": "abc", "name": "file.pdf"}]
    mock_psycopg2_connect.return_value = _make_mock_conn(rows)

    returned_sql, result = text_to_sql_module.text_to_sql("List my documents", user_id)

    assert returned_sql == raw_sql
    assert not result.startswith("[text_to_sql error:")
    assert "abc" in result


def test_plain_fenced_sql_is_accepted(monkeypatch, mock_psycopg2_connect):
    """LLM wraps SQL in plain ``` fences (no language tag); fences must be stripped."""
    user_id = "test-user-123"
    raw_sql = f"SELECT id FROM documents WHERE user_id = '{user_id}'"
    fenced_sql = f"```\n{raw_sql}\n```"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(fenced_sql))

    rows = [{"id": "abc"}]
    mock_psycopg2_connect.return_value = _make_mock_conn(rows)

    returned_sql, result = text_to_sql_module.text_to_sql("List document IDs", user_id)

    assert returned_sql == raw_sql
    assert not result.startswith("[text_to_sql error:")


def test_rows_capped_at_100(monkeypatch, mock_psycopg2_connect):
    """fetchmany is called with 100."""
    user_id = "test-user-123"
    sql = f"SELECT id FROM documents WHERE user_id = '{user_id}'"
    monkeypatch.setattr(text_to_sql_module, "_llm", _make_mock_llm(sql))

    mock_cursor = MagicMock()
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchmany.return_value = []

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    mock_psycopg2_connect.return_value = mock_conn

    _, _ = text_to_sql_module.text_to_sql("Count docs", user_id)

    mock_cursor.fetchmany.assert_called_once_with(100)
