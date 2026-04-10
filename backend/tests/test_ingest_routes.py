from unittest.mock import MagicMock
import io
from services.metadata_service import DocumentMetadata

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
    # Ensure record_manager finds no duplicate or existing name
    monkeypatch.setattr("routers.ingest.find_duplicate_by_hash", lambda *a: None)
    monkeypatch.setattr("routers.ingest.find_document_by_name", lambda *a: None)
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

    # Stub embed_text and extract_metadata so background processing doesn't hit real APIs
    monkeypatch.setattr("routers.ingest.embed_text", lambda text: [0.0] * 5)
    monkeypatch.setattr("routers.ingest.extract_metadata", lambda text: DocumentMetadata())

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


# ---------------------------------------------------------------------------
# Record Manager integration: duplicate / update / hash storage
# ---------------------------------------------------------------------------

def test_upload_duplicate_returns_existing_doc(client, mock_supabase, monkeypatch):
    """Uploading an identical file skips re-processing and returns the existing doc."""
    existing = {"id": DOC_ID, "name": "test.txt", "storage_path": STORAGE_PATH}
    monkeypatch.setattr("routers.ingest.find_duplicate_by_hash", lambda *a: existing)

    file_content = b"Hello, this is a test document."
    response = client.post(
        "/ingest/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["document_id"] == DOC_ID
    assert data["job_id"] is None
    assert data["duplicate"] is True
    # Storage upload must NOT have been called
    mock_supabase.storage.from_.return_value.upload.assert_not_called()


def test_upload_modified_file_deletes_old(client, mock_supabase, monkeypatch):
    """Uploading a file with same name but different content deletes the old doc first."""
    old_doc = {
        "id": "old-doc-id",
        "name": "test.txt",
        "storage_path": f"{TEST_USER_ID}/old-doc-id/test.txt",
    }
    monkeypatch.setattr("routers.ingest.find_duplicate_by_hash", lambda *a: None)
    monkeypatch.setattr("routers.ingest.find_document_by_name", lambda *a: old_doc)

    mock_supabase.storage.from_.return_value.upload.return_value = MagicMock()
    mock_supabase.storage.from_.return_value.remove.return_value = MagicMock()
    mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    call_count = {"n": 0}

    def _insert_side_effect(payload):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.execute.return_value.data = [{"id": DOC_ID}]
        else:
            result.execute.return_value.data = [{"id": JOB_ID}]
        return result

    mock_supabase.table.return_value.insert = _insert_side_effect
    monkeypatch.setattr("routers.ingest.embed_text", lambda text: [0.0] * 5)
    monkeypatch.setattr("routers.ingest.extract_metadata", lambda text: DocumentMetadata())

    file_content = b"This is modified content."
    response = client.post(
        "/ingest/upload",
        files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "document_id" in data  # UUID is generated by router, not predictable
    assert data["duplicate"] is False
    # Old storage file must have been removed
    mock_supabase.storage.from_.return_value.remove.assert_called_once_with(
        [old_doc["storage_path"]]
    )


def test_upload_new_file_stores_hash(client, mock_supabase, monkeypatch):
    """Uploading a new file stores content_hash in the documents insert payload."""
    monkeypatch.setattr("routers.ingest.find_duplicate_by_hash", lambda *a: None)
    monkeypatch.setattr("routers.ingest.find_document_by_name", lambda *a: None)

    mock_supabase.storage.from_.return_value.upload.return_value = MagicMock()

    captured_payload = {}
    call_count = {"n": 0}

    def _insert_side_effect(payload):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            captured_payload.update(payload)
            result.execute.return_value.data = [{"id": DOC_ID}]
        else:
            result.execute.return_value.data = [{"id": JOB_ID}]
        return result

    mock_supabase.table.return_value.insert = _insert_side_effect
    monkeypatch.setattr("routers.ingest.embed_text", lambda text: [0.0] * 5)
    monkeypatch.setattr("routers.ingest.extract_metadata", lambda text: DocumentMetadata())

    file_content = b"Brand new file content."
    response = client.post(
        "/ingest/upload",
        files={"file": ("new.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200
    assert "content_hash" in captured_payload
    assert len(captured_payload["content_hash"]) == 64  # SHA-256 hex length


# ---------------------------------------------------------------------------
# Metadata: extraction result stored on documents row
# ---------------------------------------------------------------------------

def test_process_document_stores_metadata(client, mock_supabase, monkeypatch):
    """_process_document must include metadata in the documents.update() payload."""
    monkeypatch.setattr("routers.ingest.find_duplicate_by_hash", lambda *a: None)
    monkeypatch.setattr("routers.ingest.find_document_by_name", lambda *a: None)

    mock_supabase.storage.from_.return_value.upload.return_value = MagicMock()

    call_count = {"n": 0}

    def _insert_side_effect(payload):
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.execute.return_value.data = [{"id": DOC_ID}]
        else:
            result.execute.return_value.data = [{"id": JOB_ID}]
        return result

    mock_supabase.table.return_value.insert = _insert_side_effect
    monkeypatch.setattr("routers.ingest.embed_text", lambda text: [0.0] * 5)

    extracted = DocumentMetadata(
        title="My Report",
        summary="A short summary.",
        document_type="report",
        topics=["finance", "q4"],
        language="en",
    )
    monkeypatch.setattr("routers.ingest.extract_metadata", lambda text: extracted)

    # Capture the payload passed to documents.update()
    captured_update = {}

    original_update = mock_supabase.table.return_value.update

    def _update_side_effect(payload):
        captured_update.update(payload)
        return original_update(payload)

    mock_supabase.table.return_value.update = _update_side_effect

    file_content = b"A financial report for Q4 2024."
    response = client.post(
        "/ingest/upload",
        files={"file": ("report.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert response.status_code == 200

    # The documents.update() call must carry status + metadata
    assert captured_update.get("status") == "complete"
    meta = captured_update.get("metadata", {})
    assert meta.get("title") == "My Report"
    assert meta.get("document_type") == "report"
    assert meta.get("language") == "en"
    # None fields must be excluded from JSONB payload
    assert "author" not in meta
    assert "date" not in meta
