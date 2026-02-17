"""Notificações pendentes de lembretes removidos (at_ms no passado).

Para evitar spam no WhatsApp, a mensagem só é enviada após o cliente ter
enviado 2 mensagens na mesma sessão (incrementamos a cada mensagem do user).
"""

from typing import Any

from backend.locale import LangCode

_PENDING: dict[tuple[str, str], dict[str, Any]] = {}
# Estrutura: (channel, chat_id) -> { "removed_jobs": [{"id": str, "name": str}], "user_msg_count": int }
REQUIRED_MSGS_BEFORE_NOTIFY = 2


def _key(channel: str, chat_id: str) -> tuple[str, str]:
    return (channel, str(chat_id))


def register_pending_stale_notification(
    channel: str,
    chat_id: str,
    removed_jobs: list[dict[str, str]],
) -> None:
    """Regista que foram removidos lembretes obsoletos para este chat. A mensagem será enviada após 2 msgs do user."""
    if not removed_jobs:
        return
    key = _key(channel, chat_id)
    existing = _PENDING.get(key)
    if existing:
        existing["removed_jobs"].extend(removed_jobs)
        existing["user_msg_count"] = 0
    else:
        _PENDING[key] = {
            "removed_jobs": list(removed_jobs),
            "user_msg_count": 0,
        }


def maybe_get_stale_notification(channel: str, chat_id: str, lang: LangCode = "pt-BR") -> tuple[bool, str | None]:
    """
    Chamado a cada mensagem do utilizador. Incrementa o contador; se >= 2,
    devolve (True, mensagem) e limpa o pendente. Caso contrário (False, None).
    """
    key = _key(channel, chat_id)
    entry = _PENDING.get(key)
    if not entry:
        return (False, None)
    entry["user_msg_count"] = entry.get("user_msg_count", 0) + 1
    if entry["user_msg_count"] < REQUIRED_MSGS_BEFORE_NOTIFY:
        return (False, None)
    removed = entry.get("removed_jobs") or []
    del _PENDING[key]
    if not removed:
        return (False, None)
    msg = _format_notification(removed, lang)
    return (True, msg)


def _format_notification(removed_jobs: list[dict[str, str]], lang: LangCode) -> str:
    """Mensagem de desculpa, o que foi removido e que já aprendemos."""
    lines_pt_pt = [
        "Peço desculpa. Alguns lembretes estavam com data/hora no passado (erro nosso) e foram removidos:",
    ]
    lines_pt_br = [
        "Peço desculpas. Alguns lembretes estavam com data/hora no passado (erro nosso) e foram removidos:",
    ]
    lines_es = [
        "Lo siento. Algunos recordatorios tenían fecha/hora en el pasado (error nuestro) y fueron eliminados:",
    ]
    lines_en = [
        "I'm sorry. Some reminders had a date/time in the past (our mistake) and were removed:",
    ]
    for j in removed_jobs[:10]:
        name = (j.get("name") or j.get("id") or "?").strip()[:50]
        lines_pt_pt.append(f"• {name}")
        lines_pt_br.append(f"• {name}")
        lines_es.append(f"• {name}")
        lines_en.append(f"• {name}")
    if len(removed_jobs) > 10:
        extra = f" (+{len(removed_jobs) - 10} mais)"
        lines_pt_pt.append(extra)
        lines_pt_br.append(extra)
        lines_es.append(f" (+{len(removed_jobs) - 10} más)")
        lines_en.append(f" (+{len(removed_jobs) - 10} more)")
    closing_pt_pt = "Já corrigi isto; o erro não se vai repetir. Se quiseres, podes criar os lembretes de novo."
    closing_pt_br = "Já corrigi isso; o erro não vai se repetir. Se quiser, pode criar os lembretes de novo."
    closing_es = "Ya lo corregí; el error no se repetirá. Si quieres, puedes crear los recordatorios de nuevo."
    closing_en = "I've fixed this; the error won't happen again. If you like, you can create the reminders again."
    if lang == "pt-PT":
        return "\n".join(lines_pt_pt) + "\n\n" + closing_pt_pt
    if lang == "es":
        return "\n".join(lines_es) + "\n\n" + closing_es
    if lang == "en":
        return "\n".join(lines_en) + "\n\n" + closing_en
    return "\n".join(lines_pt_br) + "\n\n" + closing_pt_br
