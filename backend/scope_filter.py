"""Scope filter: detect if user input is organizer-scope (agenda/reminder/list)."""

import re
from pathlib import Path
from backend.logger import get_logger

logger = get_logger(__name__)

# Keywords that indicate in-scope (comandos e intenções)

# Keywords that indicate in-scope (comandos e intenções)
SCOPE_KEYWORDS = re.compile(
    r"\b(lembrete|lembrar|lembre|lista|listar|list|mercado|compras|pendentes|"
    r"receitas?(?!\s+(federal|estadual|municipal|fiscal|bruta|l[íi]quida|da\s+empresa|financeira|tribut[aá]ria))|ingredientes|cad[eê]|"
    r"add|remover|remove|feito|delete|filme|livro|musica|evento|"
    r"agendar|agenda|daqui a|em \d+ (min|hora|dia)|todo dia|toda semana|"
    r"diariamente|recorrente|mensalmente|a cada \d+ (min|hora|dia)|"
    r"preciso\s+ir|tenho\s+(consulta|reunião|reuniao)|ir\s+ao\s+(m[eé]dico|dentista)|"
    r"m[eé]dico|medico|consulta|dentista|reunião|reuniao|"
    r"/lembrete|/list|/filme|/recorrente|/nuke|/reset|/bomba|/agenda|/stats|/fuso|/tz|/lang|/help|/ajuda|"
    r"apaga tudo|reset total)\b",
    re.I,
)

_SCOPE_PROMPT_FALLBACK = """Analise se a mensagem do usuário é sobre: agenda/eventos (compromissos com data), lembrete, listas (compras, filmes, livros, músicas, notas, sites, to-dos), ou comando organizacional (/lembrete, /list, /filme, /recorrente).
Responda apenas: SIM ou NAO
- SIM = escopo do organizador (lembretes, agenda/eventos, listas, comandos /list etc)
- NAO = conversa geral, política, opiniões, perguntas fora do tema

Mensagem: "{input}"
"""


_SCOPE_PROMPT_CACHE = None

def _load_scope_prompt() -> str:
    """Load prompt from prompts/scope_filter.txt or use fallback (cached)."""
    global _SCOPE_PROMPT_CACHE
    if _SCOPE_PROMPT_CACHE is not None:
        return _SCOPE_PROMPT_CACHE

    for base in (Path(__file__).resolve().parent.parent, Path.home() / ".zapista"):
        path = base / "prompts" / "scope_filter.txt"
        if path.exists():
            _SCOPE_PROMPT_CACHE = path.read_text(encoding="utf-8").strip()
            return _SCOPE_PROMPT_CACHE

    _SCOPE_PROMPT_CACHE = _SCOPE_PROMPT_FALLBACK
    return _SCOPE_PROMPT_CACHE



def _is_affirmative(raw: str) -> bool:
    if not raw:
        return False
    first_word = raw.split()[0].rstrip(".,!?;:").upper()
    return first_word in {"SIM", "YES", "SI", "SÍ", "S", "Y"}


def _is_negative(raw: str) -> bool:
    if not raw:
        return False
    first_word = raw.split()[0].rstrip(".,!?;:").upper()
    return first_word in {"NAO", "NÃO", "NO", "N"}


def is_in_scope_fast(text: str) -> bool:
    """Quick regex/keyword check. Use for MVP without LLM call."""
    if not text or not text.strip():
        return False
    t = text.strip()
    # Qualquer comando slash é considerado in-scope por definição
    if t.startswith("/"):
        logger.info("scope_filter_decision", extra={"extra": {"in_scope": True, "method": "slash_command"}})
        return True
    res = bool(SCOPE_KEYWORDS.search(t))
    logger.info("scope_filter_decision", extra={"extra": {"in_scope": res, "method": "regex"}})
    return res


async def is_in_scope_llm(text: str, provider=None, model: str | None = None) -> bool:
    """
    Call LLM (Xiaomi MiMo, DeepSeek, etc.) for SIM/NAO. One cheap completion, no tools.
    If provider is None or call fails, fallback to is_in_scope_fast.
    """
    if not text or not text.strip():
        return False
    t = text.strip()
    # Qualquer comando slash é considerado in-scope por definição (não deixar o LLM recusar)
    if t.startswith("/"):
        logger.info("scope_filter_decision", extra={"extra": {"in_scope": True, "method": "slash_command"}})
        return True
    if provider is None:
        return is_in_scope_fast(t)
    try:
        prompt_template = _load_scope_prompt()
        user_content = prompt_template.replace("{input}", text.strip())
        messages = [{"role": "user", "content": user_content}]
        import time
        start_t = time.perf_counter()
        response = await provider.chat(
            messages=messages,
            tools=None,
            model=model,
            max_tokens=10,
            temperature=0,
        )
        latency_ms = int((time.perf_counter() - start_t) * 1000)
        
        if not response or not response.content:
            res = is_in_scope_fast(text)
            logger.info("scope_filter_decision", extra={"extra": {"in_scope": res, "method": "llm_fallback", "error": "empty_response"}})
            return res
            
        raw = response.content.strip().upper()
        res = False
        if _is_affirmative(raw):
            res = True
        elif _is_negative(raw):
            res = False
        else:
            res = is_in_scope_fast(text)
            
        logger.info("scope_filter_decision", extra={"extra": {"in_scope": res, "method": "llm", "latency_ms": latency_ms}})
        return res
    except Exception as e:
        res = is_in_scope_fast(text)
        logger.warning("scope_filter_llm_error", extra={"extra": {"in_scope": res, "method": "llm_error", "error": str(e)}})
        return res


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
        if _is_affirmative(raw):
            return True
        if _is_negative(raw):
            return False
        return False
    except Exception:
        return False
