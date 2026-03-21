"""
Notificações atrasadas de lembretes removidos (jobs "at" no passado).

A limpeza diária remove esses jobs e regista aqui. A mensagem de desculpa
só é enviada após 2 mensagens do cliente na mesma sessão (anti-spam WhatsApp).
"""

import json
import os
from pathlib import Path
from typing import Any

_MESSAGES_UNTIL_SEND = 2


def _store_path() -> Path:
    try:
        from zapista.config.loader import get_data_dir
        d = get_data_dir() / "cron"
    except Exception:
        d = Path(os.environ.get("ZAPISTA_DATA", os.path.expanduser("~/.zapista"))) / "cron"
    d.mkdir(parents=True, exist_ok=True)
    return d / "stale_removal_pending.json"


def _key(channel: str, chat_id: str) -> str:
    return f"{channel}:{chat_id}"


def _load() -> dict[str, Any]:
    p = _store_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict[str, Any]) -> None:
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def add_removals(
    channel: str,
    chat_id: str,
    removed_jobs: list[tuple[str, str]],
    phone_for_locale: str | None = None,
) -> None:
    """
    Regista que foram removidos lembretes para (channel, chat_id).
    removed_jobs: [(job_id, job_name), ...]
    phone_for_locale: número real do utilizador (para resolver idioma de @lid).
    A notificação será enviada após 2 mensagens do cliente.
    """
    if not removed_jobs:
        return
    data = _load()
    key = _key(channel, chat_id)
    existing = data.get(key, {"removed": [], "messages_until_send": _MESSAGES_UNTIL_SEND})
    existing["removed"] = existing.get("removed", []) + [list(r) for r in removed_jobs]
    existing["messages_until_send"] = _MESSAGES_UNTIL_SEND
    # Guardar phone_for_locale para resolver idioma de @lid
    if phone_for_locale and not existing.get("phone_for_locale"):
        existing["phone_for_locale"] = phone_for_locale
    data[key] = existing
    _save(data)


def consume(channel: str, chat_id: str) -> tuple[bool, str | None]:
    """
    Chamado a cada mensagem do cliente. Decrementa o contador.
    Quando chega a 0, retorna (True, mensagem_de_desculpa) e remove o pendente.
    Caso contrário (False, None).
    """
    data = _load()
    key = _key(channel, chat_id)
    entry = data.get(key)
    if not entry:
        return False, None
    count = entry.get("messages_until_send", _MESSAGES_UNTIL_SEND)
    count -= 1
    if count > 0:
        entry["messages_until_send"] = count
        data[key] = entry
        _save(data)
        return False, None
    # Enviar agora
    removed = entry.get("removed", [])
    phone_for_locale = entry.get("phone_for_locale")
    del data[key]
    _save(data)
    if not removed:
        return False, None
    return True, _build_apology_message(channel, chat_id, removed, phone_for_locale=phone_for_locale)


def _build_apology_message(
    channel: str,
    chat_id: str,
    removed: list[list[str]],
    phone_for_locale: str | None = None,
) -> str:
    """Mensagem de desculpa no idioma do utilizador."""
    lang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        from backend.locale import STALE_REMOVAL_APOLOGY
        db = SessionLocal()
        try:
            # Passa phone_for_locale para resolver @lid → idioma correto (ex.: +351 → pt-PT)
            lang = get_user_language(db, chat_id, phone_for_locale) or "pt-BR"
        finally:
            db.close()
    except Exception:
        try:
            from backend.locale import phone_to_default_language
            # Tenta pelo número real; fallback ao chat_id
            lang = phone_to_default_language(phone_for_locale or chat_id) or "pt-BR"
        except Exception:
            pass
    from backend.locale import STALE_REMOVAL_APOLOGY
    template = STALE_REMOVAL_APOLOGY.get(lang, STALE_REMOVAL_APOLOGY["pt-BR"])
    names = [r[1] if len(r) > 1 and r[1] else r[0] for r in removed]
    # Truncate to max 10 names to avoid overwhelming WhatsApp messages
    MAX_DISPLAY = 10
    if len(names) > MAX_DISPLAY:
        shown = names[:MAX_DISPLAY]
        extra = len(names) - MAX_DISPLAY
        extra_label = {"pt-PT": f"… e mais {extra}", "pt-BR": f"… e mais {extra}", "es": f"… y {extra} más", "en": f"… and {extra} more"}
        list_part = ", ".join(shown) + " " + extra_label.get(lang, extra_label["en"])
    else:
        list_part = ", ".join(names)
    return template.format(removed_list=list_part, count=len(removed))
