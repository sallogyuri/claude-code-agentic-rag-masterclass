from unittest.mock import MagicMock
from services.record_manager import compute_file_hash, find_duplicate_by_hash, find_document_by_name


# ---------------------------------------------------------------------------
# compute_file_hash
# ---------------------------------------------------------------------------

def test_compute_file_hash_deterministic():
    data = b"hello world"
    assert compute_file_hash(data) == compute_file_hash(data)


def test_compute_file_hash_different_content():
    assert compute_file_hash(b"file version 1") != compute_file_hash(b"file version 2")


def test_compute_file_hash_returns_hex_string():
    result = compute_file_hash(b"some bytes")
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex is always 64 chars


# ---------------------------------------------------------------------------
# find_duplicate_by_hash
# ---------------------------------------------------------------------------

def test_find_duplicate_by_hash_found():
    doc = {"id": "doc-1", "name": "notes.txt", "storage_path": "user/doc-1/notes.txt"}
    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .neq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = [doc]

    result = find_duplicate_by_hash(mock_supabase, "user-1", "abc123")
    assert result == doc


def test_find_duplicate_by_hash_not_found():
    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .neq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = []

    result = find_duplicate_by_hash(mock_supabase, "user-1", "abc123")
    assert result is None


def test_find_duplicate_by_hash_ignores_error_documents():
    """Error-status documents must not block re-uploads of the same content."""
    mock_supabase = MagicMock()
    # Simulate no rows returned (because .neq filters out the error doc)
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .neq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = []

    result = find_duplicate_by_hash(mock_supabase, "user-1", "hash-of-failed-pdf")
    assert result is None
    # Confirm .neq("status", "error") was called on the chain
    neq_call = (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .neq
    )
    neq_call.assert_called_once_with("status", "error")


# ---------------------------------------------------------------------------
# find_document_by_name
# ---------------------------------------------------------------------------

def test_find_document_by_name_found():
    doc = {"id": "doc-2", "name": "report.md", "storage_path": "user/doc-2/report.md"}
    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = [doc]

    result = find_document_by_name(mock_supabase, "user-1", "report.md")
    assert result == doc


def test_find_document_by_name_not_found():
    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = []

    result = find_document_by_name(mock_supabase, "user-1", "report.md")
    assert result is None
