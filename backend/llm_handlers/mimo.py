"""Helper: chamada ao Mimo (scope_provider) para formatação."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


async def call_mimo(
    ctx: "HandlerContext",
    user_lang: str,
    instruction: str,
    data_text: str,
    max_tokens: int = 420,
) -> str | None:
    """Chama o Mimo (scope_provider) para gerar resposta. Retorna None se não houver provider."""
    if not ctx.scope_provider or not ctx.scope_model:
        return None
    try:
        lang_instruction = {
            "pt-PT": "Responde em português de Portugal. Resposta curta (1-2 frases).",
            "pt-BR": "Responde em português do Brasil. Resposta curta (1-2 frases).",
            "es": "Responde en español. Respuesta corta (1-2 frases).",
            "en": "Respond in English. Short answer (1-2 sentences).",
        }.get(user_lang, "Respond in the user's language. Short answer (1-2 sentences).")
        prompt = f"{instruction}\n\n{lang_instruction}\n\nDados:\n{data_text}"
        r = await ctx.scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ctx.scope_model,
            profile="parser",
        )
        out = (r.content or "").strip()
        return out if out else None
    except Exception:
        return None
