"""Search tool: busca na web via Perplexity API para listas, músicas, filmes, receitas, etc."""

import re
from typing import Any

from zapista.agent.tools.base import Tool
from backend.search_guardrails import is_search_reasonable, is_absurd_search

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"
MAX_RESULTS = 5
SEARCH_TIMEOUT = 25.0  # Aumentado para receitas/pesquisas
MAX_RETRIES = 2

# Query é receita/ingredientes → fallback para Chat API quando search falha
_RECIPE_QUERY_RE = re.compile(
    r"\b(receita|receitas|ingredientes?|lista\s+de\s+ingredientes|como\s+fazer)\b",
    re.I,
)


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

    async def _call_search_api(self, q: str) -> dict | None:
        """Chama a API de search. Retorna data ou None em erro."""
        import httpx
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
                    r = await client.post(
                        PERPLEXITY_SEARCH_URL,
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"query": q, "max_results": MAX_RESULTS},
                    )
                    r.raise_for_status()
                    return r.json()
            except Exception:
                if attempt == MAX_RETRIES - 1:
                    return None
        return None

    async def _call_chat_fallback(self, q: str) -> str | None:
        """Fallback: Perplexity Chat API para receitas quando search falha."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=45.0) as client:
                r = await client.post(
                    PERPLEXITY_CHAT_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "sonar",
                        "messages": [
                            {"role": "system", "content": "Lista ingredientes ou passos. Formato claro, numerado. Português."},
                            {"role": "user", "content": q},
                        ],
                        "max_tokens": 1024,
                        "temperature": 0.2,
                    },
                )
                r.raise_for_status()
                data = r.json()
                choices = data.get("choices") or []
                if choices:
                    msg = choices[0].get("message") or {}
                    return (msg.get("content") or "").strip()
        except Exception:
            pass
        return None

    async def execute(self, query: str = "", **kwargs: Any) -> str:
        if not self._api_key:
            return "Error: Perplexity API not configured. Set ZAPISTA_PROVIDERS__PERPLEXITY__API_KEY."
        q = (query or "").strip()
        absurd = is_absurd_search(q)
        if absurd:
            return absurd
        if not is_search_reasonable(q):
            return (
                "Busca fora do escopo. Use apenas para: listas, músicas, filmes, livros, receitas, "
                "convidados, sugestões de organização."
            )

        data = await self._call_search_api(q)
        if data:
            results = data.get("results") or []
            if results:
                lines = []
                for i, hit in enumerate(results[:MAX_RESULTS], 1):
                    title = hit.get("title") or ""
                    snippet = hit.get("snippet") or ""
                    lines.append(f"{i}. **{title}**\n   {snippet[:200]}{'…' if len(snippet) > 200 else ''}")
                return "**Resultados da busca:**\n\n" + "\n\n".join(lines)
            if not results:
                return "Nenhum resultado encontrado."

        # Search falhou: para receitas, tentar Chat API como fallback
        if _RECIPE_QUERY_RE.search(q):
            chat_result = await self._call_chat_fallback(q)
            if chat_result:
                return f"**Resultado (receita):**\n\n{chat_result}"

        return "Erro na busca. Tenta de novo em instantes."
