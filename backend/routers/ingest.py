from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks
from supabase import create_client, Client
from config import settings
from auth import get_current_user
from services.chunking_service import chunk_text
from services.embedding_service import embed_text
from services.record_manager import compute_file_hash, find_duplicate_by_hash, find_document_by_name
from services.metadata_service import extract_metadata
import uuid

router = APIRouter()

supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
)


def _process_document(document_id: str, job_id: str, file_bytes: bytes, user_id: str) -> None:
    try:
        # Mark job as processing
        supabase.table("ingestion_jobs").update({"status": "processing"}).eq("id", job_id).execute()

        # Decode text (UTF-8 only — plaintext and markdown)
        text = file_bytes.decode("utf-8")

        # Extract metadata BEFORE chunking — needs full document text
        metadata = extract_metadata(text)

        # Chunk
        chunks = chunk_text(text)

        # Embed and collect rows
        rows = []
        for i, chunk in enumerate(chunks):
            embedding = embed_text(chunk)
            rows.append({
                "document_id": document_id,
                "user_id": user_id,
                "content": chunk,
                "chunk_index": i,
                "embedding": embedding,
            })

        # Batch insert chunks
        supabase.table("chunks").insert(rows).execute()

        # Single update: status + metadata (exclude None fields from JSONB)
        supabase.table("documents").update({
            "status": "complete",
            "metadata": metadata.model_dump(exclude_none=True),
        }).eq("id", document_id).execute()
        supabase.table("ingestion_jobs").update({"status": "complete"}).eq("id", job_id).execute()

    except Exception as e:
        supabase.table("documents").update({"status": "error"}).eq("id", document_id).execute()
        supabase.table("ingestion_jobs").update({
            "status": "error",
            "error_message": str(e),
        }).eq("id", job_id).execute()


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    filename = file.filename or "upload"

    file_bytes = await file.read()
    content_hash = compute_file_hash(file_bytes)

    # Case 1: Exact duplicate — same content already ingested, skip re-processing
    existing = find_duplicate_by_hash(supabase, user_id, content_hash)
    if existing:
        return {"document_id": existing["id"], "job_id": None, "duplicate": True}

    # Case 2: Same filename, different content — replace the old document
    old = find_document_by_name(supabase, user_id, filename)
    if old:
        try:
            supabase.storage.from_("documents").remove([old["storage_path"]])
        except Exception:
            pass
        supabase.table("documents").delete().eq("id", old["id"]).execute()

    document_id = str(uuid.uuid4())
    storage_path = f"{user_id}/{document_id}/{filename}"

    # Upload to Supabase Storage
    try:
        supabase.storage.from_("documents").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "text/plain"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {e}")

    # Insert documents row
    doc_result = supabase.table("documents").insert({
        "id": document_id,
        "user_id": user_id,
        "name": filename,
        "size": len(file_bytes),
        "mime_type": file.content_type or "text/plain",
        "storage_path": storage_path,
        "status": "pending",
        "content_hash": content_hash,
    }).execute()

    if not doc_result.data:
        raise HTTPException(status_code=500, detail="Failed to create document record")

    # Insert ingestion job
    job_result = supabase.table("ingestion_jobs").insert({
        "document_id": document_id,
        "user_id": user_id,
        "status": "pending",
    }).execute()

    job_id = job_result.data[0]["id"]

    # Queue background processing
    background_tasks.add_task(_process_document, document_id, job_id, file_bytes, user_id)

    return {"document_id": document_id, "job_id": job_id, "duplicate": False}


@router.get("/documents")
def list_documents(user: dict = Depends(get_current_user)):
    result = (
        supabase.table("documents")
        .select("id, name, size, mime_type, status, created_at, metadata")
        .eq("user_id", user["user_id"])
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, user: dict = Depends(get_current_user)):
    user_id = user["user_id"]

    # Fetch document to verify ownership and get storage path
    result = (
        supabase.table("documents")
        .select("id, storage_path")
        .eq("id", document_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = result.data[0]["storage_path"]

    # Delete from Storage (best-effort — don't block on failure)
    try:
        supabase.storage.from_("documents").remove([storage_path])
    except Exception:
        pass

    # Delete document row — chunks and ingestion_jobs cascade
    supabase.table("documents").delete().eq("id", document_id).eq("user_id", user_id).execute()
