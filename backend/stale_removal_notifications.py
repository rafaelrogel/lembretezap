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


def add_removals(channel: str, chat_id: str, removed_jobs: list[tuple[str, str]]) -> None:
    """
    Regista que foram removidos lembretes para (channel, chat_id).
    removed_jobs: [(job_id, job_name), ...]
    A notificação será enviada após 2 mensagens do cliente.
    """
    if not removed_jobs:
        return
    data = _load()
    key = _key(channel, chat_id)
    existing = data.get(key, {"removed": [], "messages_until_send": _MESSAGES_UNTIL_SEND})
    existing["removed"] = existing.get("removed", []) + [list(r) for r in removed_jobs]
    existing["messages_until_send"] = _MESSAGES_UNTIL_SEND
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
    del data[key]
    _save(data)
    if not removed:
        return False, None
    return True, _build_apology_message(channel, chat_id, removed)


def _build_apology_message(channel: str, chat_id: str, removed: list[list[str]]) -> str:
    """Mensagem de desculpa no idioma do utilizador."""
    lang = "pt-BR"
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        from backend.locale import phone_to_default_language, STALE_REMOVAL_APOLOGY, LangCode
        db = SessionLocal()
        try:
            lang = get_user_language(db, chat_id) or "pt-BR"
        finally:
            db.close()
    except Exception:
        try:
            from backend.locale import phone_to_default_language
            lang = phone_to_default_language(chat_id) or "pt-BR"
        except Exception:
            pass
    from backend.locale import STALE_REMOVAL_APOLOGY
    template = STALE_REMOVAL_APOLOGY.get(lang, STALE_REMOVAL_APOLOGY["pt-BR"])
    names = [r[1] if len(r) > 1 and r[1] else r[0] for r in removed]
    list_part = ", ".join(names)
    return template.format(removed_list=list_part, count=len(removed))
