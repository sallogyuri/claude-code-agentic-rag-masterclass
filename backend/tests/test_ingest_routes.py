from unittest.mock import MagicMock
import io

TEST_USER_ID = "test-user-id"
DOC_ID = "doc-abc-123"
JOB_ID = "job-xyz-456"
STORAGE_PATH = f"{TEST_USER_ID}/{DOC_ID}/test.txt"


# ---------------------------------------------------------------------------
# GET /ingest/documents
# ---------------------------------------------------------------------------

def test_list_documents_returns_data(client, mock_supabase):
    docs = [
        {
            "id": DOC_ID,
            "name": "test.txt",
            "size": 100,
            "mime_type": "text/plain",
            "status": "complete",
            "created_at": "2024-01-01",
        }
    ]
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
        .data
    ) = docs

    response = client.get("/ingest/documents")
    assert response.status_code == 200
    assert response.json() == docs


# ---------------------------------------------------------------------------
# POST /ingest/upload
# ---------------------------------------------------------------------------

def test_upload_document_returns_ids(client, mock_supabase, monkeypatch):
    # Storage upload succeeds silently
    mock_supabase.storage.from_.return_value.upload.return_value = MagicMock()

    # Track insert calls: first is documents, second is ingestion_jobs
    call_count = {"n": 0}

    def _insert_side_effect(payload):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            # documents insert
            result.execute.return_value.data = [{"id": DOC_ID}]
        else:
            # ingestion_jobs insert
            result.execute.return_value.data = [{"id": JOB_ID}]
        return result

    mock_supabase.table.return_value.insert = _insert_side_effect

    # Stub embed_text so background processing doesn't hit real API
    monkeypatch.setattr("routers.ingest.embed_text", lambda text: [0.0] * 5)

    file_content = b"Hello, this is a test document."
    response = client.post(
        "/ingest/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data
    assert "job_id" in data


# ---------------------------------------------------------------------------
# DELETE /ingest/documents/{document_id}
# ---------------------------------------------------------------------------

def test_delete_document_returns_204(client, mock_supabase):
    # Document found with ownership
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = [{"id": DOC_ID, "storage_path": STORAGE_PATH}]

    mock_supabase.storage.from_.return_value.remove.return_value = MagicMock()
    mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock()

    response = client.delete(f"/ingest/documents/{DOC_ID}")
    assert response.status_code == 204


def test_delete_missing_document_returns_404(client, mock_supabase):
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = []

    response = client.delete("/ingest/documents/nonexistent-id")
    assert response.status_code == 404
