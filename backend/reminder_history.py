"""Histórico de pedidos e lembretes para o cliente rever e para análises («rever lembretes», «quantos esta semana?»)."""

from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from backend.models_db import ReminderHistory
from backend.user_store import get_or_create_user

_MAX_PER_USER_PER_KIND = 20  # manter últimos N por tipo


def add_scheduled(
    db: Session,
    chat_id: str,
    message: str,
    *,
    job_id: str | None = None,
    schedule_at: datetime | None = None,
    channel: str | None = None,
    recipient: str | None = None,
) -> None:
    """Regista um pedido de lembrete agendado (para rever depois)."""
    user = get_or_create_user(db, chat_id)
    row = ReminderHistory(
        user_id=user.id,
        kind="scheduled",
        message=(message or "").strip() or "Lembrete",
        job_id=(job_id or "")[:64] if job_id else None,
        schedule_at=schedule_at,
        channel=(channel or "")[:32] if channel else None,
        recipient=(recipient or "")[:256] if recipient else None,
        status="scheduled",
    )
    db.add(row)
    _trim_history(db, user.id)
    db.commit()


def add_delivered(db: Session, chat_id: str, message: str) -> None:
    """Regista uma lembrança entregue (texto que foi enviado ao cliente).
    Usado quando não há job_id para correlacionar (fallback).
    """
    user = get_or_create_user(db, chat_id)
    row = ReminderHistory(
        user_id=user.id,
        kind="delivered",
        message=(message or "").strip() or "",
        status="sent",
        delivered_at=datetime.utcnow(),
    )
    db.add(row)
    _trim_history(db, user.id)
    db.commit()


def update_on_delivery(
    db: Session,
    chat_id: str,
    job_id: str,
    message: str,
    *,
    failed: bool = False,
    provider_error: str | None = None,
) -> bool:
    """Atualiza o registo agendado correspondente ao job_id para status=sent ou failed.
    Retorna True se encontrou e atualizou; False se não encontrou (caller pode usar add_delivered).
    """
    user = get_or_create_user(db, chat_id)
    row = (
        db.query(ReminderHistory)
        .filter(
            ReminderHistory.user_id == user.id,
            ReminderHistory.job_id == job_id,
            ReminderHistory.status == "scheduled",
        )
        .first()
    )
    if not row:
        return False
    row.kind = "delivered"
    row.message = (message or "").strip() or row.message
    row.status = "failed" if failed else "sent"
    row.delivered_at = datetime.utcnow()
    row.provider_error = (provider_error or "")[:256] if provider_error else None
    db.commit()
    return True


def _trim_history(db: Session, user_id: int) -> None:
    """Mantém apenas os últimos _MAX_PER_USER_PER_KIND por kind por user.
    Nota: os callers (add_scheduled, add_delivered) fazem db.commit(); não fazemos commit aqui.
    """
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
    from sqlalchemy import func

    row = (
        db.query(ReminderHistory)
        .filter(
            ReminderHistory.user_id == user.id,
            ReminderHistory.kind == "delivered",
        )
        .order_by(
            func.coalesce(ReminderHistory.delivered_at, ReminderHistory.created_at).desc()
        )
        .first()
    )
    return row.message if row and row.message else None


def get_reminder_history(
    db: Session,
    chat_id: str,
    kind: Literal["scheduled", "delivered"] | None = None,
    limit: int = 100,
    since: datetime | None = None,
    include_executed: bool = True,
) -> list[dict]:
    """
    Lista entradas do histórico de lembretes.
    Retorna lista de dicts com: kind, message, created_at, schedule_at, status, delivered_at, job_id, channel, recipient.
    """
    user = get_or_create_user(db, chat_id)
    q = db.query(ReminderHistory).filter(ReminderHistory.user_id == user.id)
    if kind:
        q = q.filter(ReminderHistory.kind == kind)
    if since is not None:
        q = q.filter(ReminderHistory.created_at >= since)
    rows = q.order_by(ReminderHistory.created_at.desc()).limit(limit).all()
    result = []
    for r in rows:
        # Incluir executados (sent/failed) como "entregues" para «rever lembretes»
        if not include_executed and r.status in ("sent", "failed"):
            continue
        result.append({
            "kind": r.kind,
            "message": (r.message or "").strip(),
            "created_at": r.created_at,
            "schedule_at": r.schedule_at,
            "status": r.status,
            "delivered_at": r.delivered_at,
            "job_id": r.job_id,
            "channel": r.channel,
            "recipient": r.recipient,
        })
    return result
