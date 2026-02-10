"""Estado do fluxo /restart: confirmação em duas etapas (sim/não) e execução do reset."""

import time
from typing import Any

# (channel, chat_id) -> "1" (primeira confirmação) ou "2" (segunda)
_STATE: dict[tuple[str, str], tuple[str, float]] = {}  # (channel, chat_id) -> (stage, ts)
_EXPIRY_SECONDS = 600  # 10 min


def _key(channel: str, chat_id: str) -> tuple[str, str]:
    return (channel, str(chat_id))


def get_restart_stage(channel: str, chat_id: str) -> str | None:
    """"1" = à espera da primeira confirmação, "2" = à espera da segunda. None = inativo ou expirado."""
    key = _key(channel, chat_id)
    entry = _STATE.get(key)
    if not entry:
        return None
    stage, ts = entry
    if time.time() - ts > _EXPIRY_SECONDS:
        del _STATE[key]
        return None
    return stage


def set_restart_stage(channel: str, chat_id: str, stage: str) -> None:
    _STATE[_key(channel, chat_id)] = (stage, time.time())


def clear_restart_stage(channel: str, chat_id: str) -> None:
    _STATE.pop(_key(channel, chat_id), None)


# Mensagens do fluxo (WhatsApp: * = negrito)
MSG_FIRST = (
    "Queres reiniciar toda a tua sessão e voltar ao zero? "
    "Responde *sim* ou *não*."
)
MSG_SECOND = (
    "⚠️ Última confirmação: vais reiniciar toda a conversa e apagar "
    "*todos os lembretes*, *compromissos agendados*, *tarefas*, *listas* — "
    "tudo volta à estaca zero. Esta ação não tem volta.\n\n"
    "Confirma com *sim* ou *não*."
)
MSG_CANCELLED = "Reinício cancelado. Nada foi alterado."
MSG_DONE = "Tudo reiniciado. É um novo começo."


def is_confirm_reply(content: str) -> bool:
    t = (content or "").strip().lower()
    return t in ("sim", "s", "não", "nao", "n", "1", "2", "yes", "no", "y")


def is_confirm_yes(content: str) -> bool:
    t = (content or "").strip().lower()
    return t in ("sim", "s", "yes", "y", "1")


def is_confirm_no(content: str) -> bool:
    t = (content or "").strip().lower()
    return t in ("não", "nao", "n", "no", "2")


async def run_restart(
    channel: str,
    chat_id: str,
    *,
    session_manager: Any,
    cron_service: Any,
) -> None:
    """
    Executa o restart completo: apaga sessão, lembretes (cron) deste chat, listas e eventos no DB.
    """
    from loguru import logger
    session_key = f"{channel}:{chat_id}"
    # 1) Sessão (histórico de conversa)
    try:
        if session_manager.delete(session_key):
            logger.info(f"Restart: session deleted {session_key}")
    except Exception as e:
        logger.warning(f"Restart: session delete failed: {e}")
    # 2) Cron jobs cujo payload.to == chat_id e payload.channel == channel
    try:
        for job in cron_service.list_jobs(include_disabled=True):
            p = getattr(job, "payload", None)
            if p and getattr(p, "channel", None) == channel and getattr(p, "to", None) == chat_id:
                cron_service.remove_job(job.id)
                logger.info(f"Restart: cron job removed {job.id}")
    except Exception as e:
        logger.warning(f"Restart: cron remove failed: {e}")
    # 3) Listas e eventos do utilizador (backend DB)
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_or_create_user
        from backend.models_db import List, ListItem, Event
        db = SessionLocal()
        try:
            user = get_or_create_user(db, chat_id)
            for lst in db.query(List).filter(List.user_id == user.id).all():
                db.query(ListItem).filter(ListItem.list_id == lst.id).delete()
                db.delete(lst)
            db.query(Event).filter(Event.user_id == user.id).delete()
            db.commit()
            logger.info(f"Restart: lists and events deleted for chat_id={chat_id[:20]}...")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Restart: db cleanup failed: {e}")
