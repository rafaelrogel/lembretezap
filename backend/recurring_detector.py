"""
Detecta se um lembrete parece recorrente e solicita a recorrência ao utilizador.
Usa lista de 500 padrões; se fora da lista, usa MIMO para classificar.
"""

from backend.recurring_patterns import (
    is_in_recurring_list,
    looks_like_reminder_without_time,
)
from backend.locale import LangCode

# Mensagens para solicitar recorrência nos 4 idiomas
ASK_RECURRENCE_MSG: dict[LangCode, str] = {
    "pt-PT": "Parece recorrente. Qual a frequência? Ex: todo dia às 8h ou a cada 12h.",
    "pt-BR": "Parece recorrente. Qual a frequência? Ex: todo dia às 8h ou a cada 12h.",
    "es": "Parece recurrente. ¿Con qué frecuencia? Ej: cada día a las 8h o cada 12h.",
    "en": "Looks recurring. How often? E.g. every day at 8am or every 12h.",
}


def get_ask_recurrence_message(lang: LangCode = "pt-BR") -> str:
    """Mensagem para solicitar a recorrência ao utilizador."""
    return ASK_RECURRENCE_MSG.get(lang, ASK_RECURRENCE_MSG["pt-BR"])


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


async def maybe_ask_recurrence(
    content: str,
    lang: LangCode,
    scope_provider=None,
    scope_model: str = "",
) -> str | None:
    """
    Se o conteúdo for pedido de lembrete sem tempo E parecer recorrente,
    retorna a mensagem para solicitar recorrência. Caso contrário, None.
    Também trata /lembrete X quando X não tem tempo (via command_parser).
    """
    is_reminder, msg_extract = looks_like_reminder_without_time(content)
    if not is_reminder or not msg_extract:
        return None
    is_rec = await is_likely_recurring(msg_extract, scope_provider, scope_model)
    if not is_rec:
        return None
    return get_ask_recurrence_message(lang)
