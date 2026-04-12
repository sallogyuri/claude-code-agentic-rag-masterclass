# CLAUDE.md

RAG app with chat (default) and document ingestion interfaces. Config via env vars, no admin UI.

## Stack
- Frontend: React + Vite + Tailwind + shadcn/ui
- Backend: Python + FastAPI
- Database: Supabase (Postgres, pgvector, Auth, Storage, Realtime)
- LLM: OpenAI (Module 1), OpenRouter (Module 2+)
- Observability: LangSmith

## Rules
- Python backend must use a `venv` virtual environment
- No LangChain, no LangGraph - raw SDK calls only
- Use Pydantic for structured LLM outputs
- All tables need Row-Level Security - users only see their own data
- Stream chat responses via SSE
- Use Supabase Realtime for ingestion status updates
- Module 2+ uses stateless completions - store and send chat history yourself
- Ingestion is manual file upload only - no connectors or automated pipelines

## Planning
- Save all plans to `.agent/plans/` folder
- Naming convention: `{sequence}.{plan-name}.md` (e.g., `1.auth-setup.md`, `2.document-ingestion.md`)
- Plans should be detailed enough to execute without ambiguity
- Each task in the plan must include at least one validation test to verify it works
- Assess complexity and single-pass feasibility - can an agent realistically complete this in one go?
- Include a complexity indicator at the top of each plan:
  - ✅ **Simple** - Single-pass executable, low risk
  - ⚠️ **Medium** - May need iteration, some complexity
  - 🔴 **Complex** - Break into sub-plans before executing

## Development Flow
1. **Plan** - Create a detailed plan and save it to `.agent/plans/`
2. **Build** - Execute the plan to implement the feature
3. **Validate** - Test and verify the implementation works correctly. Use browser testing where applicable via an appropriate MCP
4. **Iterate** - Fix any issues found during validation

## Starting Services

Run `./start.sh` from the project root to start both servers:
- **Backend** (FastAPI + uvicorn): http://127.0.0.1:8000
- **Frontend** (Vite dev server): http://localhost:5173

The script activates the backend `venv` automatically. Press Ctrl+C to stop all services.

To start manually:
- Backend: `cd backend && source venv/Scripts/activate && uvicorn main:app --reload --port 8000`
- Frontend: `cd frontend && npm run dev`

## Test Credentials
For browser testing and validation:
- **Email:** test@test.com
- **Password:** testuser

For testing the isolation of data between users:
- **Email:** test2@test.com
- **Password:** testuser2

## Validation

### Regression suite

Run when the user ask to run regression testing:

```bash
cd backend && source venv/Scripts/activate && pytest tests/ -v
```

All external dependencies (Supabase, OpenAI, JWKS) are mocked — no live credentials required.

| Test file | Coverage |
|-----------|----------|
| `tests/test_chunking.py` | `chunk_text` edge cases (empty, single, multi-chunk, overlap, custom params) |
| `tests/test_health.py` | GET /health smoke test |
| `tests/test_auth.py` | JWT middleware: missing header (401), expired token (401), valid token (200) |
| `tests/test_chat_routes.py` | GET /chat/threads, GET messages, unowned thread 404, POST /chat/stream SSE |
| `tests/test_ingest_routes.py` | GET /ingest/documents, POST upload, DELETE 204, DELETE 404, duplicate detection, update flow, hash storage, metadata storage |
| `tests/test_llm_service.py` | Direct text stream, tool-call round-trip, no content leak during tool phase |
| `tests/test_metadata_service.py` | `extract_metadata` success, partial JSON, LLM failure, invalid JSON, model_dump exclude_none |
| `tests/test_record_manager.py` | compute_file_hash determinism/uniqueness, find_duplicate_by_hash found/not-found, find_document_by_name found/not-found |
| `tests/test_parsing_service.py` | `extract_text` fast path (txt/md), Docling routing (pdf/docx/html), fallback (unknown UTF-8/binary), temp file cleanup on success and failure |

### Adding tests for new features

**Every new backend feature must include tests.** When implementing a new route, service, or piece of logic:

1. Add tests to the relevant existing file (e.g., a new `/chat` endpoint goes in `tests/test_chat_routes.py`), or create a new `tests/test_<feature>.py` if the feature is distinct enough.
2. Add any new external dependencies (new clients, APIs) to the module-level mocks in `tests/conftest.py` before the app is imported — follow the existing `patch(...)` pattern.
3. Update the coverage table above with the new file/tests.
4. Run the full suite and confirm 0 failures before committing.

## Progress
Check PROGRESS.md for current module status. Update it as you complete tasks.