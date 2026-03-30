from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    openai_api_key: str
    openai_assistant_id: str = ""

    langsmith_api_key: str
    langsmith_project: str = "rag-masterclass-module1"
    langsmith_tracing_v2: str = "true"

    allowed_origins: str = "http://localhost:5173"


settings = Settings()
