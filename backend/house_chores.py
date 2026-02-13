"""
Módulo de limpeza da casa: tarefas com frequency (weekly/bi-weekly) e rotação entre pessoas.

Tarefas pré-definidas do catálogo. Uma pessoa define tarefas e pessoas; o sistema rotaciona.
"""

from datetime import datetime, timedelta
from typing import Any

from zoneinfo import ZoneInfo
from loguru import logger
from sqlalchemy.orm import Session

from backend.models_db import HouseChoreTask, HouseChorePerson
from backend.house_chores_catalog import CHORE_CATALOG, get_chore_name
from backend.user_store import get_or_create_user, get_user_timezone, get_user_language, is_user_in_quiet_window
from backend.database import SessionLocal


WEEKDAY_NAMES_PT = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def is_task_due_today(task: HouseChoreTask, today: datetime.date, tz: ZoneInfo) -> bool:
    """True se a tarefa deve ser lembrada hoje. today em timezone local."""
    # weekday: 0=seg, 6=dom (Python)
    if today.weekday() != task.weekday:
        return False
    if task.frequency == "weekly":
        return True
    if task.frequency == "bi-weekly":
        # A cada 2 semanas: semanas 0, 2, 4... desde criação da tarefa
        ref = task.created_at.date() if task.created_at else today
        days_diff = (today - ref).days
        if days_diff < 0:
            return False
        weeks_since = days_diff // 7
        return weeks_since % 2 == 0
    return False


def get_next_person(task: HouseChoreTask, persons: list[HouseChorePerson], db: Session) -> str | None:
    """Retorna o nome da próxima pessoa na rotação. Atualiza last_person_idx."""
    if not persons or not task.rotation_enabled:
        return None
    n = len(persons)
    idx = (task.last_person_idx + 1) % n
    task.last_person_idx = idx
    db.commit()
    return persons[idx].name


def get_due_chores(db: Session, chat_id: str) -> list[dict[str, Any]]:
    """Lista tarefas que vencem hoje para o utilizador. Retorna [{task, name, assigned_to}, ...]."""
    user = get_or_create_user(db, chat_id)
    tz_iana = get_user_timezone(db, chat_id) or "UTC"
    try:
        tz = ZoneInfo(tz_iana)
    except Exception:
        tz = ZoneInfo("UTC")
    today = datetime.now(tz).date()

    persons = list(db.query(HouseChorePerson).filter(
        HouseChorePerson.user_id == user.id
    ).order_by(HouseChorePerson.order_idx, HouseChorePerson.id))

    tasks = db.query(HouseChoreTask).filter(HouseChoreTask.user_id == user.id).all()
    result = []
    for t in tasks:
        if not is_task_due_today(t, today, tz):
            continue
        name = t.custom_name or get_chore_name(t.catalog_slug)
        assigned = get_next_person(t, persons, db) if t.rotation_enabled and persons else None
        result.append({
            "task": t,
            "name": name,
            "assigned_to": assigned,
        })
    return result


def build_chore_reminder_message(chores: list[dict], user_lang: str) -> str:
    """Constrói mensagem de lembrete das tarefas de hoje."""
    if not chores:
        return ""
    lines = ["🧹 **Limpeza hoje**"]
    for c in chores:
        name = c.get("name", "")
        who = c.get("assigned_to")
        if who:
            lines.append(f"• {name} — vez de **{who}**")
        else:
            lines.append(f"• {name}")
    return "\n".join(lines)


async def run_house_chores_daily(
    *,
    bus: Any,
    session_manager: Any,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Verifica tarefas de limpeza devidas hoje para cada utilizador e envia lembrete.
    Janela: 8h–10h local. Retorna (enviados, erros).
    """
    from zapista.bus.events import OutboundMessage

    sent = 0
    errors = 0

    sessions = session_manager.list_sessions()
    for s in sessions:
        key = s.get("key") or ""
        if ":" not in key:
            continue
        channel, chat_id = key.split(":", 1)
        if not chat_id:
            continue
        ch = channel if channel else default_channel
        if ch != "whatsapp":
            continue

        try:
            db = SessionLocal()
            try:
                if is_user_in_quiet_window(chat_id):
                    continue
                tz_iana = get_user_timezone(db, chat_id) or "UTC"
                try:
                    tz = ZoneInfo(tz_iana)
                except Exception:
                    tz = ZoneInfo("UTC")
                now_local = datetime.now(tz)
                if not (8 <= now_local.hour < 10):
                    continue

                chores = get_due_chores(db, chat_id)
                if not chores:
                    continue

                user_lang = get_user_language(db, chat_id)
                content = build_chore_reminder_message(chores, user_lang)
                if not content:
                    continue
            finally:
                db.close()

            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=chat_id,
                content=content,
                metadata={"priority": "high"},
            ))
            sent += 1
            logger.info(f"House chores reminder sent to {chat_id[:20]}...")
        except Exception as e:
            errors += 1
            logger.warning(f"House chores failed for {key}: {e}")

    return sent, errors
