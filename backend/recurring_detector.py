"""
Detecta se um lembrete parece recorrente e solicita a recorrência ao utilizador.
Usa lista de 500 padrões; se fora da lista, usa MIMO para classificar.
"""

from backend.recurring_patterns import (
    is_in_recurring_list,
    looks_like_reminder_without_time,
)
from backend.locale import LangCode

# Mensagens para solicitar quando/frequência (lembrete sem tempo)
ASK_WHEN_MSG: dict[LangCode, str] = {
    "pt-PT": "Quando queres o lembrete? Ex: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h.",
    "pt-BR": "Quando você quer o lembrete? Ex: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h.",
    "es": "¿Cuándo quieres el recordatorio? Ej: en 10 min, mañana a las 8h, cada día a las 10h o cada 2h.",
    "en": "When do you want the reminder? E.g. in 10 min, tomorrow at 8am, every day at 10am or every 2h.",
}
# Alias para compatibilidade
ASK_RECURRENCE_MSG = ASK_WHEN_MSG


def get_ask_recurrence_message(lang: LangCode = "pt-BR") -> str:
    """Mensagem para solicitar quando/frequência ao utilizador."""
    return ASK_WHEN_MSG.get(lang, ASK_WHEN_MSG["pt-BR"])


async def is_likely_recurring(
    message: str,
    scope_provider=None,
    scope_model: str = "",
) -> bool:
    """
    True se o lembrete parece recorrente (medicamento, exercício, etc.).
    1) Verifica a lista de 500 padrões.
    2) Se não estiver na lista, usa MIMO para classificar.
    """
    if not message or len((message or "").strip()) < 3:
        return False
    msg = (message or "").strip()
    if is_in_recurring_list(msg):
        return True
    if not scope_provider or not scope_model:
        return False
    try:
        prompt = (
            f"The user wants a reminder: «{msg[:250]}». "
            "Is this typically a RECURRING event (e.g. medication, exercise, meals, hygiene, pets, house chores)? "
            "Reply ONLY: SIM or NAO (or YES/NO)."
        )
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=10,
            temperature=0,
        )
        raw = (r.content or "").strip().upper()
        return "SIM" in raw or "YES" in raw or raw.startswith("S") or raw.startswith("Y")
    except Exception:
        return False


def _has_explicit_time(content: str) -> bool:
    """True se o conteúdo já indica quando (a cada, em X min, daqui a, amanhã, etc)."""
    import re
    t = (content or "").strip().lower()
    if not t or len(t) < 5:
        return False
    patterns = [
        r"a\s+cada\s+\d+",
        r"em\s+\d+\s*(min|hora|dia)",
        r"daqui\s+a\s+\d+",
        r"amanh[ãa]",
        r"todo\s+dia",
        r"diariamente",
        r"\d{1,2}\s*h\b",
        r"\d{1,2}:\d{2}",
    ]
    return any(re.search(p, t) for p in patterns)


async def maybe_ask_recurrence(
    content: str,
    lang: LangCode,
    scope_provider=None,
    scope_model: str = "",
) -> str | None:
    """
    Se o conteúdo for pedido de lembrete sem tempo explícito, retorna mensagem
    pedindo quando/frequência. Nunca deixa o agent inventar (ex: 2 min).
    - Padrões conhecidos: looks_like_reminder_without_time
    - Já tem tempo explícito (a cada 1 min, em 10 min)? Não perguntar.
    - Ambíguos: usa Mimo para classificar se é pedido de lembrete sem tempo
    """
    if _has_explicit_time(content or ""):
        return None
    is_reminder, msg_extract = looks_like_reminder_without_time(content)
    if is_reminder and msg_extract:
        return get_ask_recurrence_message(lang)
    # Fallback Mimo: mensagens curtas que podem ser lembrete sem tempo
    if (
        content
        and 10 < len((content or "").strip()) < 120
        and scope_provider
        and scope_model
    ):
        is_reminder_mimo = await _mimo_is_reminder_without_time(
            content.strip(), scope_provider, scope_model
        )
        if is_reminder_mimo:
            return get_ask_recurrence_message(lang)
    return None


async def _mimo_is_reminder_without_time(
    content: str, scope_provider, scope_model: str
) -> bool:
    """
    Usa Mimo para classificar: é pedido de lembrete sem data/hora? SIM/NAO.
    Fallback para casos que os padrões não pegam (ex: frases coloquiais).
    """
    try:
        prompt = (
            f"The user wrote: «{content[:200]}». "
            "Is this a request for a REMINDER or scheduled event WITHOUT explicit time? "
            "(e.g. 'I want to drink water', 'remind me to call João' — no 'in 5 min', 'tomorrow 8am', etc.) "
            "Reply ONLY: SIM or NAO (or YES/NO)."
        )
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=10,
            temperature=0,
        )
        raw = (r.content or "").strip().upper()
        return "SIM" in raw or "YES" in raw or raw.startswith("S") or raw.startswith("Y")
    except Exception:
        return False
