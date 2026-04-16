import psycopg2
import psycopg2.extras
import re
from openai import OpenAI
from config import settings
from langsmith import traceable

# Tables that contain per-user data and require a WHERE user_id = '...' filter.
USER_SCOPED_TABLES = {"documents", "chunks", "threads", "messages"}

# Tables exposed to the LLM — user-scoped tables plus shared/public tables.
SCHEMA_DESCRIPTION = """
User-scoped tables (rows are filtered by user_id = '<user_id>'):

documents(id UUID, user_id UUID, name TEXT, size INTEGER, mime_type TEXT, status TEXT, created_at TIMESTAMPTZ, metadata JSONB)
  - status values: 'pending' | 'processing' | 'complete' | 'error'
  - metadata keys (if present): document_type, language, author, title, summary

chunks(id UUID, document_id UUID, user_id UUID, content TEXT, chunk_index INTEGER, created_at TIMESTAMPTZ)
  - each document is split into multiple chunks

threads(id UUID, user_id UUID, title TEXT, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ)

messages(id UUID, thread_id UUID, user_id UUID, role TEXT, created_at TIMESTAMPTZ)
  - role values: 'user' | 'assistant'

Public/shared tables (no user_id column — no user filter needed):

sales_data(id SERIAL, order_id TEXT, customer_name TEXT, customer_email TEXT,
           product_name TEXT, category TEXT, quantity INTEGER, unit_price NUMERIC,
           total_amount NUMERIC, region TEXT, salesperson TEXT, order_date DATE,
           status TEXT)
  - status values: 'completed' | 'pending' | 'refunded'
  - total_amount is auto-computed as quantity * unit_price
"""

_llm = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)

SQL_GEN_PROMPT = (
    "You are a SQL expert. Generate a single valid PostgreSQL SELECT query to answer "
    "the user's question using the schema below. Rules:\n"
    "1. Only SELECT statements — no INSERT, UPDATE, DELETE, DROP, etc.\n"
    "2. For user-scoped tables (documents, chunks, threads, messages) always include "
    "WHERE user_id = '{user_id}' (or filter via JOIN) to scope results to the authenticated user.\n"
    "3. For public/shared tables (e.g. sales_data) do NOT add a user_id filter — "
    "these tables have no user_id column.\n"
    "4. Return only the SQL — no explanation, no markdown fences.\n\n"
    "Schema:\n{schema}"
)


def _strip_markdown_fences(sql: str) -> str:
    """Remove markdown code fences that LLMs sometimes add despite instructions."""
    if sql.startswith("```"):
        lines = sql.split("\n")
        # Drop the opening fence line (```sql or ```)
        lines = lines[1:]
        # Drop the closing fence line if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return sql


def _generate_sql(query: str, user_id: str) -> str:
    prompt = SQL_GEN_PROMPT.format(user_id=user_id, schema=SCHEMA_DESCRIPTION)
    response = _llm.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": query},
        ],
    )
    sql = response.choices[0].message.content.strip()
    return _strip_markdown_fences(sql)


def _validate_sql(sql: str, user_id: str) -> None:
    """Raises ValueError if SQL is not a safe SELECT.
    User-scoped tables (documents, chunks, threads, messages) must include a
    user_id filter.  Public tables (e.g. sales_data) have no user_id column so
    the check is skipped for queries that only reference public tables.
    """
    sql_lower = sql.strip().lower()
    if not sql_lower.startswith("select"):
        raise ValueError("Only SELECT queries are permitted")
    forbidden = r"\b(insert|update|delete|drop|create|alter|truncate|grant|revoke|execute|copy)\b"
    if re.search(forbidden, sql_lower):
        raise ValueError("Query contains a forbidden keyword")
    touches_user_scoped = any(table in sql_lower for table in USER_SCOPED_TABLES)
    if touches_user_scoped and user_id.lower() not in sql_lower:
        raise ValueError("Query must include user_id filter for data isolation")


def _execute_sql(sql: str) -> list[dict]:
    """Execute query in a read-only transaction, return rows as list of dicts."""
    with psycopg2.connect(settings.database_url) as conn:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchmany(100)  # cap at 100 rows
            return [dict(row) for row in rows]


@traceable(name="text_to_sql", run_type="tool")
def text_to_sql(query: str, user_id: str) -> tuple[str, str]:
    """
    Translate a natural-language query into SQL, execute it, and return (sql, result).
    sql is the generated query (empty string on error).
    result is the formatted table string, a 'no results' message, or an error string.
    Never raises — errors are returned as the second element of the tuple.
    """
    try:
        sql = _generate_sql(query, user_id)
        print(f"[text_to_sql] generated SQL: {sql!r}", flush=True)
        _validate_sql(sql, user_id)
        print(f"[text_to_sql] validation passed, executing...", flush=True)
        rows = _execute_sql(sql)
        print(f"[text_to_sql] execution succeeded, {len(rows)} rows", flush=True)
    except Exception as e:
        import traceback
        print(f"[text_to_sql] FAILED: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return ("", f"[text_to_sql error: {e}]")

    if not rows:
        return (sql, "Query returned no results.")

    # Format as a readable table-like string
    headers = list(rows[0].keys())
    lines = [" | ".join(headers)]
    lines.append("-" * len(lines[0]))
    for row in rows:
        lines.append(" | ".join(str(row[h]) for h in headers))
    return (sql, "\n".join(lines))
