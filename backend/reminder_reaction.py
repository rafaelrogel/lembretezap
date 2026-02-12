"""Mapeamento message_id → job_id e tratamento de reações (emoji = feito / não feito)."""

from sqlalchemy.orm import Session

from backend.models_db import SentReminderMapping

# Emojis positivos = tarefa feita (remove/desativa job)
EMOJI_POSITIVE = frozenset({
    "👍", "✅", "✔", "✔️", "😊", "🙂", "😁", "✓", "★", "⭐", "💯",
    "+1", "thumbsup", "white_check_mark", "check", "heavy_check_mark",
})
# Emojis negativos = tarefa não feita (perguntar reagendamento)
# ⏰ é tratado separadamente (soneca)
EMOJI_NEGATIVE = frozenset({
    "👎", "❌", "✗", "✘", "😞", "🙁", "😕", "🔄",
    "-1", "thumbsdown", "x", "cross_mark",
})

# Emojis soneca = adiar 5 min (máx 3 vezes)
EMOJI_SNOOZE = frozenset({"⏰", "alarm", "clock"})


def store_sent_mapping(db: Session, chat_id: str, message_id: str, job_id: str) -> None:
    """Regista mapeamento (chat_id, message_id) → job_id para reações."""
    if not message_id or not job_id:
        return
    row = SentReminderMapping(
        chat_id=(chat_id or "")[:256],
        message_id=(message_id or "")[:64],
        job_id=(job_id or "")[:64],
    )
    db.add(row)
    db.commit()


def lookup_job_by_message(db: Session, chat_id: str, message_id: str) -> str | None:
    """Retorna job_id se existir mapeamento. Remove o mapeamento após lookup (usa só uma vez)."""
    if not message_id or not chat_id:
        return None
    row = (
        db.query(SentReminderMapping)
        .filter(
            SentReminderMapping.chat_id == chat_id,
            SentReminderMapping.message_id == message_id,
        )
        .first()
    )
    if not row:
        return None
    job_id = row.job_id
    db.delete(row)
    db.commit()
    return job_id


def is_positive_emoji(emoji: str) -> bool:
    """True se emoji indica tarefa feita."""
    if not emoji:
        return False
    e = (emoji or "").strip().lower()
    return e in EMOJI_POSITIVE


def is_negative_emoji(emoji: str) -> bool:
    """True se emoji indica tarefa não feita."""
    if not emoji:
        return False
    e = (emoji or "").strip().lower()
    return e in EMOJI_NEGATIVE


def is_snooze_emoji(emoji: str) -> bool:
    """True se emoji indica soneca (adiar 5 min, máx 3 vezes)."""
    if not emoji:
        return False
    e = (emoji or "").strip().lower()
    return e in EMOJI_SNOOZE
