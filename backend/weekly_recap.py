"""
Resumo da semana / Resumo do mês: automático (tarefas feitas, lembretes, eventos).

Política: o resumo NÃO é enviado proativamente. É entregue no primeiro contacto do
cliente após o período (aproveitando a sessão aberta por ele). /resumo e /resumo mes
continuam a mostrar o resumo a pedido.
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


def get_month_stats(db, chat_id: str, end_date_local, tz, up_to_today=None) -> dict[str, Any]:
    """
    Estatísticas do utilizador no mês de end_date_local (1º ao último dia do mês, ou até up_to_today se dado).
    up_to_today: quando definido (ex.: para "mês corrente"), o fim do período é min(up_to_today, último dia do mês).
    Retorna: tarefas_feitas, lembretes_recebidos, eventos_criados, inicio, fim (dd/mm).
    """
    from calendar import monthrange
    user = get_or_create_user(db, chat_id)
    year, month = end_date_local.year, end_date_local.month
    start_date = end_date_local.replace(day=1)
    last_day = monthrange(year, month)[1]
    last_day_date = end_date_local.replace(day=last_day)
    end_date = min(up_to_today, last_day_date) if up_to_today else last_day_date

    start_naive = datetime(
        start_date.year, start_date.month, start_date.day, 0, 0, 0,
        tzinfo=tz
    ).astimezone(timezone.utc).replace(tzinfo=None)
    end_naive = datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59,
        tzinfo=tz
    ).astimezone(timezone.utc).replace(tzinfo=None)

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
        "fim": end_date.strftime("%d/%m"),
    }


def get_pending_recap_on_first_contact(db, chat_id: str, tz: ZoneInfo):
    """
    Calcula se há resumo semanal e/ou mensal pendente para entregar no primeiro contacto.
    Política: apenas semana corrente (últimos 7 dias até hoje) e mês corrente (1º do mês até hoje).
    Retorna: (weekly_content, weekly_period_id, monthly_content, monthly_period_id).
    """
    today = datetime.now(tz).date()
    # Semana corrente: 7 dias terminando em hoje
    weekly_period_id = f"{today.year}-W{today.isocalendar()[1]:02d}"
    # Mês corrente: 1º do mês até hoje
    monthly_period_id = today.strftime("%Y-%m")

    user_lang = get_user_language(db, chat_id)
    preferred_name = get_user_preferred_name(db, chat_id)
    stats_w = get_week_stats(db, chat_id, today, tz)
    weekly_content = build_weekly_recap_text(
        stats=stats_w,
        user_lang=user_lang,
        preferred_name=preferred_name,
    )
    stats_m = get_month_stats(db, chat_id, today, tz, up_to_today=today)
    monthly_content = build_monthly_recap_text(
        stats=stats_m,
        user_lang=user_lang,
        preferred_name=preferred_name,
    )
    return weekly_content, weekly_period_id, monthly_content, monthly_period_id


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
        header = f"📊 **Resumo da semana** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo da tua semana:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Ótima semana! 💪"
    elif user_lang == "es":
        header = f"📊 **Resumen de la semana** ({inicio}–{fim})"
        line1 = f"Hola, {name}! Resumen de tu semana:"
        line2 = f"• {tf} tareas completadas"
        line3 = f"• {lr} recordatorios recibidos"
        line4 = f"• {ev} eventos creados"
        footer = "¡Buena semana! 💪"
    elif user_lang == "en":
        header = f"📊 **Week summary** ({inicio}–{fim})"
        line1 = f"Hi {name}! Here's your week in a nutshell:"
        line2 = f"• {tf} tasks completed"
        line3 = f"• {lr} reminders received"
        line4 = f"• {ev} events created"
        footer = "Great week! 💪"
    else:
        header = f"📊 **Resumo da semana** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo da tua semana:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Ótima semana! 💪"

    lines = [header, "", line1, line2, line3, line4, "", footer]
    return "\n".join(lines)


def build_monthly_recap_text(
    *,
    stats: dict[str, Any],
    user_lang: str,
    preferred_name: str | None,
) -> str:
    """
    Constrói o texto do resumo do mês (sem LLM).
    """
    name = (preferred_name or "").strip() or "utilizador"
    tf = stats.get("tarefas_feitas", 0)
    lr = stats.get("lembretes_recebidos", 0)
    ev = stats.get("eventos_criados", 0)
    inicio = stats.get("inicio", "")
    fim = stats.get("fim", "")

    if user_lang == "pt-BR":
        header = f"📊 **Resumo do mês** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo do teu mês:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Bom mês! 💪"
    elif user_lang == "es":
        header = f"📊 **Resumen del mes** ({inicio}–{fim})"
        line1 = f"Hola, {name}! Resumen de tu mes:"
        line2 = f"• {tf} tareas completadas"
        line3 = f"• {lr} recordatorios recibidos"
        line4 = f"• {ev} eventos creados"
        footer = "¡Buen mes! 💪"
    elif user_lang == "en":
        header = f"📊 **Month summary** ({inicio}–{fim})"
        line1 = f"Hi {name}! Here's your month in a nutshell:"
        line2 = f"• {tf} tasks completed"
        line3 = f"• {lr} reminders received"
        line4 = f"• {ev} events created"
        footer = "Great month! 💪"
    else:
        header = f"📊 **Resumo do mês** ({inicio}–{fim})"
        line1 = f"Olá, {name}! Aqui vai o resumo do teu mês:"
        line2 = f"• {tf} tarefas concluídas"
        line3 = f"• {lr} lembretes recebidos"
        line4 = f"• {ev} eventos criados"
        footer = "Bom mês! 💪"

    lines = [header, "", line1, line2, line3, line4, "", footer]
    return "\n".join(lines)


async def run_weekly_recap(
    *,
    bus: Any,
    session_manager: Any,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Não envia proativamente. O resumo da semana é entregue no primeiro contacto
    do cliente (ver get_pending_recap_on_first_contact no agent loop).
    Retorna (0, 0).
    """
    logger.debug("Weekly recap: not sending proactively (delivered on first contact)")
    return 0, 0


async def run_monthly_recap(
    *,
    bus: Any,
    session_manager: Any,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Não envia proativamente. O resumo do mês é entregue no primeiro contacto
    do cliente (ver get_pending_recap_on_first_contact no agent loop).
    Retorna (0, 0).
    """
    logger.debug("Monthly recap: not sending proactively (delivered on first contact)")
    return 0, 0
