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

    database_url: str = ""          # Supabase Postgres connection string (pooled)
    tavily_api_key: str = ""        # Tavily web search API key

    langsmith_api_key: str
    langsmith_project: str = "rag-masterclass-module2"
    langsmith_tracing_v2: str = "true"

    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176"


settings = Settings()

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to four tools:\n"
    "- retrieve_chunks: search the user's uploaded documents for relevant content\n"
    "- text_to_sql: query structured/tabular data — use for (1) questions about the "
    "user's documents, threads, or messages (counts, status, file types, metadata) and "
    "(2) business or analytics questions about sales data (revenue, orders, customers, "
    "regions, salespeople, products, date ranges)\n"
    "- web_search: search the web when the knowledge base has no relevant results\n"
    "- spawn_sub_agent: delegate full-document analysis to an isolated sub-agent\n\n"
    "Always try retrieve_chunks first for document content questions. "
    "Use text_to_sql for any structured/tabular data question, including sales analytics. "
    "Use web_search as a fallback only when retrieve_chunks finds nothing relevant or "
    "the question clearly requires current/external information. "
    "Cite web sources (title + URL) when using web_search results."
)
