"""Search tool: busca na web via Perplexity API para listas, músicas, filmes, receitas, etc."""

from typing import Any

from nanobot.agent.tools.base import Tool
from backend.search_guardrails import is_search_reasonable, is_absurd_search

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
MAX_RESULTS = 5  # API com orçamento limitado; mínimo necessário para enriquecer lista


class SearchTool(Tool):
    """Search the web via Perplexity to enrich lists/events — scope-limited, use sparingly."""

    def __init__(self, api_key: str):
        self._api_key = (api_key or "").strip()

    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search the web to ENRICH list/event content. Use ONLY when user explicitly asks for "
            "suggestions, rankings, or curated info (e.g. 'melhores livros de Jorge Amado', "
            "'top músicas dance 2023', 'receitas de massa'). Do NOT search if you can answer from "
            "your knowledge. One search per turn max. Budget limited. query: search terms."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (e.g. 'melhores músicas dance 2023', 'top recipes pasta')",
                    "maxLength": 200,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", **kwargs: Any) -> str:
        if not self._api_key:
            return "Error: Perplexity API not configured. Set NANOBOT_PROVIDERS__PERPLEXITY__API_KEY."
        q = (query or "").strip()
        absurd = is_absurd_search(q)
        if absurd:
            return absurd
        if not is_search_reasonable(q):
            return (
                "Busca fora do escopo. Use apenas para: listas, músicas, filmes, livros, receitas, "
                "convidados, sugestões de organização."
            )
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(
                    PERPLEXITY_SEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"query": q, "max_results": MAX_RESULTS},
                )
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as e:
            return f"Erro na busca: {e.response.status_code}"
        except Exception as e:
            return f"Erro na busca: {e}"
        results = data.get("results") or []
        if not results:
            return "Nenhum resultado encontrado."
        lines = []
        for i, hit in enumerate(results[:MAX_RESULTS], 1):
            title = hit.get("title") or ""
            snippet = hit.get("snippet") or ""
            url = hit.get("url") or ""
            lines.append(f"{i}. **{title}**\n   {snippet[:200]}{'…' if len(snippet) > 200 else ''}")
        return "**Resultados da busca:**\n\n" + "\n\n".join(lines)
