import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import chat, ingest

# LangSmith env vars (must be set before any langsmith import)
os.environ["LANGCHAIN_TRACING_V2"] = settings.langsmith_tracing_v2
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

app = FastAPI(title="RAG Masterclass API", version="2.0.0")

_configured_origins = [o.strip() for o in settings.allowed_origins.split(",")]
# Also permit any localhost port (Vite shifts ports when the default is occupied)
import re as _re
_localhost_origins = [
    o for o in _configured_origins
    if _re.match(r"https?://localhost(:\d+)?$", o)
]
_base_origins = [o for o in _configured_origins if o not in _localhost_origins]
_final_origins = _base_origins + [
    f"http://localhost:{p}" for p in range(5173, 5180)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_final_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])


@app.get("/health")
def health():
    return {"status": "ok"}
