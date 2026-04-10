import hashlib
from supabase import Client


def compute_file_hash(file_bytes: bytes) -> str:
    """Return SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def find_duplicate_by_hash(supabase: Client, user_id: str, content_hash: str) -> dict | None:
    """Return existing document row if this user already has a file with the same hash."""
    result = (
        supabase.table("documents")
        .select("id, name, storage_path")
        .eq("user_id", user_id)
        .eq("content_hash", content_hash)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def find_document_by_name(supabase: Client, user_id: str, name: str) -> dict | None:
    """Return existing document row if this user already has a file with the same name."""
    result = (
        supabase.table("documents")
        .select("id, name, storage_path")
        .eq("user_id", user_id)
        .eq("name", name)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
