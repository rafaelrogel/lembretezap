"""Histórico de pedidos e lembretes para o cliente rever e para análises («rever lembretes», «quantos esta semana?»)."""

from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from backend.models_db import ReminderHistory
from backend.user_store import get_or_create_user

_MAX_PER_USER_PER_KIND = 20  # manter últimos N por tipo


def add_scheduled(db: Session, chat_id: str, message: str) -> None:
    """Regista um pedido de lembrete agendado (para rever depois)."""
    user = get_or_create_user(db, chat_id)
    row = ReminderHistory(user_id=user.id, kind="scheduled", message=(message or "").strip() or "Lembrete")
    db.add(row)
    _trim_history(db, user.id)
    db.commit()


def add_delivered(db: Session, chat_id: str, message: str) -> None:
    """Regista uma lembrança entregue (texto que foi enviado ao cliente)."""
    user = get_or_create_user(db, chat_id)
    row = ReminderHistory(user_id=user.id, kind="delivered", message=(message or "").strip() or "")
    db.add(row)
    _trim_history(db, user.id)
    db.commit()


def _trim_history(db: Session, user_id: int) -> None:
    """Mantém apenas os últimos _MAX_PER_USER_PER_KIND por kind por user."""
    for kind in ("scheduled", "delivered"):
        rows = (
            db.query(ReminderHistory)
            .filter(ReminderHistory.user_id == user_id, ReminderHistory.kind == kind)
            .order_by(ReminderHistory.created_at.desc())
            .all()
        )
        for row in rows[_MAX_PER_USER_PER_KIND:]:
            db.delete(row)


def get_last_scheduled(db: Session, chat_id: str) -> str | None:
    """Último pedido de lembrete agendado (para «rever pedido»)."""
    user = get_or_create_user(db, chat_id)
    row = (
        db.query(ReminderHistory)
        .filter(ReminderHistory.user_id == user.id, ReminderHistory.kind == "scheduled")
        .order_by(ReminderHistory.created_at.desc())
        .first()
    )
    return row.message if row and row.message else None


def get_last_delivered(db: Session, chat_id: str) -> str | None:
    """Última lembrança entregue (para «rever lembrete»)."""
    user = get_or_create_user(db, chat_id)
    row = (
        db.query(ReminderHistory)
        .filter(ReminderHistory.user_id == user.id, ReminderHistory.kind == "delivered")
        .order_by(ReminderHistory.created_at.desc())
        .first()
    )
    return row.message if row and row.message else None


def get_reminder_history(
    db: Session,
    chat_id: str,
    kind: Literal["scheduled", "delivered"] | None = None,
    limit: int = 100,
    since: datetime | None = None,
) -> list[dict]:
    """
    Lista entradas do histórico de lembretes (para rever lembretes e análises).
    Retorna lista de {"kind": "scheduled"|"delivered", "message": str, "created_at": datetime}.
    """
    user = get_or_create_user(db, chat_id)
    q = db.query(ReminderHistory).filter(ReminderHistory.user_id == user.id)
    if kind:
        q = q.filter(ReminderHistory.kind == kind)
    if since is not None:
        q = q.filter(ReminderHistory.created_at >= since)
    rows = q.order_by(ReminderHistory.created_at.desc()).limit(limit).all()
    return [
        {"kind": r.kind, "message": (r.message or "").strip(), "created_at": r.created_at}
        for r in rows
    ]
