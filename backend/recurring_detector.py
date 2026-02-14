"""
Detecta se um lembrete parece recorrente e solicita a recorrência ao utilizador.
Usa lista de 500 padrões; se fora da lista, usa MIMO para classificar.
"""

import random

from backend.recurring_patterns import (
    is_in_recurring_list,
    looks_like_reminder_without_time,
)
from backend.locale import LangCode

# Variações por idioma — rotação para não soar sempre igual
ASK_WHEN_VARIATIONS: dict[LangCode, tuple[str, ...]] = {
    "pt-BR": (
        "Quando você quer o lembrete? Ex: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h.",
        "Em que momento quer ser lembrado? Pode ser em 10 min, amanhã 8h, todo dia ou a cada 2h.",
        "Para quando agendar? Ex: daqui 10 min, amanhã 8h, diariamente 10h ou a cada 2 horas.",
        "Me diz o horário: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h?",
        "Qual o melhor horário? Ex: em 10 min, amanhã 8h, todo dia às 10h, a cada 2h.",
    ),
    "pt-PT": (
        "Quando queres o lembrete? Ex: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h.",
        "Em que momento queres ser lembrado? Pode ser em 10 min, amanhã 8h, todo dia ou a cada 2h.",
        "Para quando agendar? Ex: daqui 10 min, amanhã 8h, diariamente 10h ou a cada 2 horas.",
        "Diz-me o horário: em 10 min, amanhã às 8h, todo dia às 10h ou a cada 2h?",
        "Qual o melhor horário? Ex: em 10 min, amanhã 8h, todo dia às 10h, a cada 2h.",
    ),
    "es": (
        "¿Cuándo quieres el recordatorio? Ej: en 10 min, mañana a las 8h, cada día a las 10h o cada 2h.",
        "¿En qué momento quieres que te recuerde? Puede ser en 10 min, mañana 8h, cada día o cada 2h.",
        "¿Para cuándo agendar? Ej: en 10 min, mañana 8h, diariamente 10h o cada 2 horas.",
        "Dime el horario: ¿en 10 min, mañana a las 8h, cada día a las 10h o cada 2h?",
        "¿Cuál es el mejor horario? Ej: en 10 min, mañana 8h, cada día 10h, cada 2h.",
    ),
    "en": (
        "When do you want the reminder? E.g. in 10 min, tomorrow at 8am, every day at 10am or every 2h.",
        "At what time would you like to be reminded? In 10 min, tomorrow 8am, daily or every 2h?",
        "When should I schedule it? E.g. in 10 min, tomorrow 8am, daily at 10am or every 2 hours.",
        "Tell me the time: in 10 min, tomorrow 8am, every day at 10am or every 2h?",
        "What's the best time? E.g. in 10 min, tomorrow 8am, daily 10am, every 2h.",
    ),
}
# Alias: primeira variante por idioma (para compatibilidade)
ASK_WHEN_MSG: dict[LangCode, str] = {
    lang: variants[0] for lang, variants in ASK_WHEN_VARIATIONS.items()
}
ASK_RECURRENCE_MSG = ASK_WHEN_MSG


def get_ask_recurrence_message(lang: LangCode = "pt-BR") -> str:
    """Mensagem para solicitar quando/frequência ao utilizador (rotação aleatória)."""
    variants = ASK_WHEN_VARIATIONS.get(lang) or ASK_WHEN_VARIATIONS["pt-BR"]
    return random.choice(variants)


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


# Palavras que indicam pedido de lembrete (para limitar quando chamar Mimo)
_REMINDER_HINT_WORDS = (
    "lembrar", "lembrete", "lembre", "recordar", "recuerdame", "remind",
    "esquecer", "forget", "recordatorio", "recordatório",
)


async def _mimo_confirms_reminder(content: str, scope_provider, scope_model: str) -> bool:
    """
    Mimo confirma: é pedido de lembrete? Usado como gate final para evitar falsos positivos.
    """
    return await _mimo_is_reminder_without_time(content, scope_provider, scope_model)


async def maybe_ask_recurrence(
    content: str,
    lang: LangCode,
    scope_provider=None,
    scope_model: str = "",
) -> str | None:
    """
    Se o conteúdo for pedido de lembrete sem tempo explícito, retorna mensagem
    pedindo quando/frequência. Nunca deixa o agent inventar (ex: 2 min).

    Fluxo: regex primeiro → Mimo como árbitro final (reduz falsos positivos).
    """
    if _has_explicit_time(content or ""):
        return None
    is_reminder, msg_extract = looks_like_reminder_without_time(content)

    if is_reminder and msg_extract:
        # Regex diz que é lembrete — Mimo confirma antes de perguntar
        if scope_provider and scope_model:
            if not await _mimo_confirms_reminder(content, scope_provider, scope_model):
                return None
        return get_ask_recurrence_message(lang)

    # Fallback: mensagem tem hint (lembrar, lembrete) mas regex não pegou
    t = (content or "").strip().lower()
    has_hint = any(w in t for w in _REMINDER_HINT_WORDS)
    if (
        content
        and 10 < len(t) < 120
        and has_hint
        and scope_provider
        and scope_model
    ):
        if await _mimo_is_reminder_without_time(
            content.strip(), scope_provider, scope_model
        ):
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
            f"O utilizador escreveu: «{content[:200]}». "
            "Isto é um pedido de LEMBRETE ou evento agendado (sem data/hora explícita)? "
            "Exemplos SIM: 'lembrar de tomar remédio', 'quero beber água', 'preciso de exercício'. "
            "Exemplos NAO: receita, lista de ingredientes, comando /audio, 'cadê a lista', pergunta geral. "
            "Responde APENAS: SIM ou NAO."
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
