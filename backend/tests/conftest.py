import os
import sys
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 1. Set env vars BEFORE any app import so pydantic-settings picks them up
# ---------------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-openai")
os.environ.setdefault("LLM_API_KEY", "sk-test-llm")
os.environ.setdefault("LLM_BASE_URL", "https://openrouter.ai/api/v1")
os.environ.setdefault("LLM_MODEL", "openai/gpt-4o-mini")
os.environ.setdefault("LLM_SYSTEM_PROMPT", "You are a test assistant.")
os.environ.setdefault("LANGSMITH_API_KEY", "ls-test")
os.environ.setdefault("LANGSMITH_PROJECT", "test-project")
os.environ.setdefault("LANGSMITH_TRACING_V2", "false")
# Disable LangSmith tracing at the SDK level
os.environ["LANGCHAIN_TRACING_V2"] = "false"

# ---------------------------------------------------------------------------
# 2. Patch module-level side-effectful constructors before app modules load
# ---------------------------------------------------------------------------
_mock_jwks_instance = MagicMock()
_jwks_patch = patch("jwt.PyJWKClient", return_value=_mock_jwks_instance)
_jwks_patch.start()

_mock_supabase = MagicMock()
_supabase_patch = patch("supabase.create_client", return_value=_mock_supabase)
_supabase_patch.start()

_mock_openai_instance = MagicMock()
_openai_patch = patch("openai.OpenAI", return_value=_mock_openai_instance)
_openai_patch.start()

# psycopg2 — prevent any real DB connection at import/test time
_psycopg2_patch = patch("psycopg2.connect", MagicMock())
_psycopg2_patch.start()

# Tavily — prevent real web requests at import/test time
_tavily_patch = patch("tavily.TavilyClient", MagicMock())
_tavily_patch.start()

# ---------------------------------------------------------------------------
# 3. Now it is safe to import the app
# ---------------------------------------------------------------------------
import pytest  # noqa: E402

# Add backend dir to path so imports resolve from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from auth import get_current_user  # noqa: E402

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------
TEST_USER = {"user_id": "test-user-id", "email": "test@test.com"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_supabase():
    """Return the shared Supabase mock so tests can configure return values."""
    _mock_supabase.reset_mock()
    # Default: record_manager lookups (select→eq→eq→limit→execute) find nothing.
    # This prevents the duplicate/update paths from firing in unrelated tests.
    (
        _mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = []
    return _mock_supabase


@pytest.fixture
def mock_openai():
    """Return the shared OpenAI mock so tests can configure return values."""
    _mock_openai_instance.reset_mock()
    return _mock_openai_instance


@pytest.fixture
def mock_jwks():
    """Return the JWKS client mock so tests can configure signing key resolution."""
    return _mock_jwks_instance


@pytest.fixture
def client(mock_supabase):
    """TestClient with auth dependency overridden to TEST_USER."""
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def raw_client(mock_supabase):
    """TestClient WITHOUT auth override — for testing auth rejection paths."""
    app.dependency_overrides.clear()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def mock_sub_agent():
    """Patch run_sub_agent_stream in the chat router to return an empty iterator."""
    with patch("routers.chat.run_sub_agent_stream", return_value=iter([])) as m:
        yield m


@pytest.fixture
def mock_psycopg2_connect():
    with patch("services.text_to_sql_service.psycopg2.connect") as m:
        yield m


@pytest.fixture
def mock_tavily():
    with patch("services.web_search_service.TavilyClient") as m:
        yield m
