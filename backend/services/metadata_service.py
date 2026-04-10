from pydantic import BaseModel
from typing import Optional
from config import settings
from services.llm_service import _client


class DocumentMetadata(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    document_type: Optional[str] = None   # "article", "report", "contract", "email", "manual", "invoice", "memo", "other"
    topics: Optional[list[str]] = None
    language: Optional[str] = None        # ISO 639-1, e.g. "en"
    author: Optional[str] = None
    date: Optional[str] = None            # ISO 8601, e.g. "2024-01-15"


def extract_metadata(text: str) -> DocumentMetadata:
    sample = text[:8000]   # headers/intro carry most metadata signal
    system_prompt = """You are a document analysis assistant. Extract metadata from the provided document text and return it as a JSON object with these exact fields:
- title: document title or descriptive name (string or null)
- summary: 1-3 sentence summary (string or null)
- document_type: one of "article", "report", "contract", "email", "manual", "invoice", "memo", "other" (string or null)
- topics: list of key topics or themes (array of strings, or null)
- language: ISO 639-1 language code e.g. "en", "fr" (string or null)
- author: author name(s) if mentioned (string or null)
- date: document date in ISO 8601 format e.g. "2024-01-15" (string or null)

Return only valid JSON. Use null for fields you cannot determine."""

    try:
        response = _client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract metadata from this document:\n\n{sample}"},
            ],
            response_format={"type": "json_object"},
            stream=False,
        )
        raw = response.choices[0].message.content or "{}"
        return DocumentMetadata.model_validate_json(raw)
    except Exception:
        # Metadata extraction is non-critical — never block ingestion
        return DocumentMetadata()
