"""Scope filter: detect if user input is organizer-scope (agenda/reminder/list)."""

import re
from pathlib import Path

# Keywords that indicate in-scope (comandos e intenções)
SCOPE_KEYWORDS = re.compile(
    r"\b(lembrete|lembrar|lembre|lista|listar|list|mercado|compras|pendentes|"
    r"receita|receitas|ingredientes|cad[eê]|"
    r"add|remover|remove|feito|delete|filme|livro|musica|evento|"
    r"agendar|agenda|daqui a|em \d+ (min|hora|dia)|todo dia|toda semana|"
    r"diariamente|recorrente|mensalmente|a cada \d+ (min|hora|dia)|"
    r"/lembrete|/list|/feito|/filme)\b",
    re.I,
)

_SCOPE_PROMPT_FALLBACK = """Analise se a mensagem do usuário é sobre: agenda, lembrete, lista (compras/pendentes), evento, filme/livro/música a anotar, ou comando organizacional (/lembrete, /list, /feito, /filme).
Responda apenas: SIM ou NAO
- SIM = é escopo do organizador (lembretes, listas, eventos, comandos /list etc)
- NAO = conversa geral, política, opiniões, perguntas fora do tema

Mensagem: "{input}"
"""


def _load_scope_prompt() -> str:
    """Load prompt from prompts/scope_filter.txt or use fallback."""
    for base in (Path(__file__).resolve().parent.parent, Path.home() / ".zapista"):
        path = base / "prompts" / "scope_filter.txt"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return _SCOPE_PROMPT_FALLBACK


def is_in_scope_fast(text: str) -> bool:
    """Quick regex/keyword check. Use for MVP without LLM call."""
    if not text or not text.strip():
        return False
    return bool(SCOPE_KEYWORDS.search(text.strip()))


async def is_in_scope_llm(text: str, provider=None, model: str | None = None) -> bool:
    """
    Call LLM (Xiaomi MiMo, DeepSeek, etc.) for SIM/NAO. One cheap completion, no tools.
    If provider is None or call fails, fallback to is_in_scope_fast.
    """
    if not text or not text.strip():
        return False
    if provider is None:
        return is_in_scope_fast(text)
    try:
        prompt_template = _load_scope_prompt()
        user_content = prompt_template.replace("{input}", text.strip())
        messages = [{"role": "user", "content": user_content}]
        response = await provider.chat(
            messages=messages,
            tools=None,
            model=model,
            max_tokens=10,
            temperature=0,
        )
        if not response or not response.content:
            return is_in_scope_fast(text)
        raw = response.content.strip().upper()
        if "SIM" in raw or raw.startswith("S"):
            return True
        if "NAO" in raw or "NÃO" in raw.upper() or raw.startswith("N"):
            return False
        # ambiguous: treat as in-scope so we don't block organizer intents
        return is_in_scope_fast(text)
    except Exception:
        return is_in_scope_fast(text)


_FOLLOW_UP_PROMPT = """O utilizador disse antes: «{prev}»
Agora disse: «{current}»

A mensagem atual é continuação do mesmo tema (lista, lembrete, compras, evento, organização)? Responde apenas: SIM ou NAO."""


async def is_follow_up_llm(
    prev_message: str,
    current_message: str,
    provider=None,
    model: str | None = None,
) -> bool:
    """
    Usa o LLM (ex.: Mimo) para decidir se a mensagem atual é follow-up da anterior.
    Só usar quando is_in_scope_fast(prev_message) é False (regex não apanhou).
    """
    if not prev_message or not (current_message or "").strip():
        return False
    if provider is None or not (model or "").strip():
        return False
    try:
        prompt = _FOLLOW_UP_PROMPT.format(
            prev=(prev_message or "")[:300],
            current=(current_message or "").strip()[:300],
        )
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            max_tokens=10,
            temperature=0,
        )
        if not response or not response.content:
            return False
        raw = response.content.strip().upper()
        if "SIM" in raw or raw.startswith("S"):
            return True
        if "NAO" in raw or "NÃO" in raw.upper() or raw.startswith("N"):
            return False
        return False
    except Exception:
        return False
