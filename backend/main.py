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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(ingest.router, prefix="/ingest", tags=["ingest"])


@app.get("/health")
def health():
    return {"status": "ok"}
