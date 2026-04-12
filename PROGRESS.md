# Progress

Track your progress through the masterclass. Update this file as you complete modules - Claude Code reads this to understand where you are in the project.

## Convention
- `[ ]` = Not started
- `[-]` = In progress
- `[x]` = Completed

## Modules

### Module 1: App Shell + Observability

- [x] Task 1: Supabase schema (supabase/migrations/001_module1_schema.sql)
- [x] Task 2: Backend scaffolding (FastAPI, config, health check)
- [x] Task 3: JWT auth middleware
- [x] Task 4: OpenAI Responses API service
- [x] Task 5: LangSmith tracing service
- [x] Task 6: Chat API router (SSE streaming, threads, messages)
- [x] Task 7: Frontend scaffolding (React + Vite + Tailwind v4 + shadcn/ui)
- [x] Task 8: Supabase client + auth hooks
- [x] Task 9: Auth UI (login/signup page)
- [x] Task 10: Chat UI with SSE streaming
- [x] Task 11: End-to-end smoke test — all layers validated

**Status:** Module 1 COMPLETE. Both servers running.

### Module 2: Document Ingestion + Custom RAG

- [x] Completed

### Module 3: Record Manager

- [x] DB migration: content_hash column + index on documents (supabase/migrations/003_module3_schema.sql)
- [x] Record manager service: SHA-256 hashing, duplicate detection, name-based lookup (backend/services/record_manager.py)
- [x] Upload handler: duplicate skip, update-in-place, hash stored on insert (backend/routers/ingest.py)
- [x] Frontend: duplicate response handling, "already up to date" feedback (useIngestion.ts, FileUpload.tsx)
- [x] Tests: 10 new tests (test_record_manager.py + extended test_ingest_routes.py), 31/31 passing

**Status:** Module 3 COMPLETE.

### Module 5: Multi-Format Support

- [x] `docling>=2.0.0` added to requirements.txt and installed in venv
- [x] `parsing_service.py`: `extract_text()` dispatcher — fast path for txt/md, Docling for pdf/docx/html, UTF-8 fallback for unknown extensions
- [x] `ingest.py`: replaced `file_bytes.decode("utf-8")` with `extract_text(file_bytes, filename)`
- [x] Frontend: file picker and instructions updated to accept .txt, .md, .pdf, .docx, .html
- [x] Tests: 10 new tests in `test_parsing_service.py`, 47/47 passing

**Status:** Module 5 COMPLETE.
