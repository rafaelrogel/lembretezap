"""
Revisão semanal: resumo automático da semana (tarefas feitas, lembretes, eventos).

Enviado automaticamente ao domingo (20h UTC) ou via comando /resumo.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from zoneinfo import ZoneInfo
from loguru import logger

from backend.models_db import ReminderHistory, AuditLog, Event
from backend.user_store import get_or_create_user, get_user_language, get_user_preferred_name, get_user_timezone


def get_week_stats(db, chat_id: str, end_date_local, tz) -> dict[str, Any]:
    """
    Estatísticas do utilizador na última semana (7 dias até end_date_local).
    Retorna: tarefas_feitas, lembretes_recebidos, eventos_criados.
    """
    user = get_or_create_user(db, chat_id)
    start_date = end_date_local - timedelta(days=6)
    start_naive = datetime(
        start_date.year, start_date.month, start_date.day, 0, 0, 0,
        tzinfo=tz
    ).astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = datetime(
        end_date_local.year, end_date_local.month, end_date_local.day, 23, 59, 59,
        tzinfo=tz
    ).astimezone(timezone.utc).replace(tzinfo=None)

    def _to_local_date(dt):
        if not dt:
            return None
        if dt.tzinfo:
            return dt.astimezone(tz).date()
        return dt.replace(tzinfo=timezone.utc).astimezone(tz).date()

    feito = (
        db.query(AuditLog)
        .filter(
            AuditLog.user_id == user.id,
            AuditLog.action == "list_feito",
            AuditLog.created_at >= start_naive,
            AuditLog.created_at <= end_naive,
        )
        .count()
    )
    lembretes = (
        db.query(ReminderHistory)
        .filter(
            ReminderHistory.user_id == user.id,
            ReminderHistory.status == "sent",
            ReminderHistory.delivered_at.isnot(None),
            ReminderHistory.delivered_at >= start_naive,
            ReminderHistory.delivered_at <= end_naive,
        )
        .count()
    )
    eventos = (
        db.query(Event)
        .filter(
            Event.user_id == user.id,
            Event.deleted == False,
            Event.created_at >= start_naive,
            Event.created_at <= end_naive,
        )
        .count()
    )

    return {
        "tarefas_feitas": feito,
        "lembretes_recebidos": lembretes,
        "eventos_criados": eventos,
        "inicio": start_date.strftime("%d/%m"),
        "fim": end_date_local.strftime("%d/%m"),
    }


def build_weekly_recap_text(
    *,
    stats: dict[str, Any],
    user_lang: str,
    preferred_name: str | None,
) -> str:
    """
    Constrói o texto do resumo semanal (sem LLM).
    """
    name = (preferred_name or "").strip() or "utilizador"
    tf = stats.get("tarefas_feitas", 0)
    lr = stats.get("lembretes_recebidos", 0)
    ev = stats.get("eventos_criados", 0)
    inicio = stats.get("inicio", "")
    fim = stats.get("fim", "")

    if user_lang == "pt-BR":
        header = f"📊 **Revisão semanal** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo da tua semana:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Ótima semana! 💪"
    elif user_lang == "es":
        header = f"📊 **Revisión semanal** ({inicio}–{fim})"
        line1 = f"Hola, {name}! Resumen de tu semana:"
        line2 = f"• {tf} tareas completadas"
        line3 = f"• {lr} recordatorios recibidos"
        line4 = f"• {ev} eventos creados"
        footer = "¡Buena semana! 💪"
    elif user_lang == "en":
        header = f"📊 **Weekly review** ({inicio}–{fim})"
        line1 = f"Hi {name}! Here's your week in a nutshell:"
        line2 = f"• {tf} tasks completed"
        line3 = f"• {lr} reminders received"
        line4 = f"• {ev} events created"
        footer = "Great week! 💪"
    else:
        header = f"📊 **Revisão semanal** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo da tua semana:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Ótima semana! 💪"

    lines = [header, "", line1, line2, line3, line4, "", footer]
    return "\n".join(lines)


async def run_weekly_recap(
    *,
    bus: Any,
    session_manager: Any,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Envia a revisão semanal a todos os utilizadores com sessão ativa.
    Usa os últimos 7 dias (até hoje no timezone de cada um).
    Retorna (enviados, erros).
    """
    from backend.database import SessionLocal
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
                user_lang = get_user_language(db, chat_id)
                preferred_name = get_user_preferred_name(db, chat_id)
                tz_iana = get_user_timezone(db, chat_id) or "UTC"
                try:
                    tz = ZoneInfo(tz_iana)
                except Exception:
                    tz = ZoneInfo("UTC")
                today = datetime.now(tz).date()
                stats = get_week_stats(db, chat_id, today, tz)
            finally:
                db.close()

            content = build_weekly_recap_text(
                stats=stats,
                user_lang=user_lang,
                preferred_name=preferred_name,
            )

            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=chat_id,
                content=content,
                metadata={"priority": "high"},
            ))
            sent += 1
            logger.info(f"Weekly recap sent to {chat_id[:20]}...")
        except Exception as e:
            errors += 1
            logger.warning(f"Weekly recap failed for {key}: {e}")

    return sent, errors
