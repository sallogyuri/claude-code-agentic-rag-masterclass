from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    openai_api_key: str  # kept for embeddings (text-embedding-3-small)

    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str
    llm_model: str = "openai/gpt-4o-mini"
    llm_system_prompt: str = (
        "You are a helpful assistant. When the user asks about documents or specific "
        "information, use the retrieve_chunks tool to search the knowledge base before answering."
    )

    langsmith_api_key: str
    langsmith_project: str = "rag-masterclass-module2"
    langsmith_tracing_v2: str = "true"

    allowed_origins: str = "http://localhost:5173"


settings = Settings()
