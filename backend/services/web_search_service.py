from tavily import TavilyClient
from config import settings
from langsmith import traceable


@traceable(name="web_search", run_type="tool")
def web_search(query: str) -> str:
    """
    Search the web using Tavily and return formatted results with source attribution.
    Returns an error string (not raised) if the search fails.
    """
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query, max_results=5, include_answer=True)
    except Exception as e:
        return f"[web_search error: {e}]"

    parts = []

    # Include Tavily's synthesized answer if present
    if response.get("answer"):
        parts.append(f"Summary: {response['answer']}\n")

    for result in response.get("results", []):
        title = result.get("title", "No title")
        url = result.get("url", "")
        content = result.get("content", "")[:400]  # trim long snippets
        parts.append(f"**{title}**\nURL: {url}\n{content}")

    return "\n\n---\n\n".join(parts) if parts else "No results found."
