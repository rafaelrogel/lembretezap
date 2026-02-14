"""Handler Pomodoro: técnica 25 min foco + 5 min pausa."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

POMODORO_WORK_MIN = 25
POMODORO_WORK_SEC = POMODORO_WORK_MIN * 60


def _is_pomodoro_job(job) -> bool:
    """True se o job é um timer de Pomodoro."""
    if not job or not job.enabled:
        return False
    name = (job.name or "").lower()
    msg = (getattr(job.payload, "message", "") or "").lower()
    jid = (job.id or "").upper()
    return (
        "pomodoro" in name or "pomodoro" in msg
        or jid.startswith("POM")
    )


async def handle_pomodoro(ctx: "HandlerContext", content: str) -> str | None:
    """
    /pomodoro — inicia timer 25 min
    /pomodoro start — mesmo
    /pomodoro stop — para o pomodoro ativo
    /pomodoro status — vê se há pomodoro correndo
    """
    t = (content or "").strip()
    if not t.lower().startswith("/pomodoro"):
        return None

    rest = t[9:].strip()  # após "/pomodoro"
    sub = (rest.split(None, 1)[0] if rest else "").lower()
    arg = rest.split(None, 1)[1].strip() if rest and len(rest.split(None, 1)) > 1 else ""

    if not ctx.cron_service or not ctx.cron_tool:
        return "🍅 Pomodoro: o cron não está disponível neste canal."

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)

    # /pomodoro stop
    if sub == "stop":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return "🍅 Nenhum Pomodoro ativo."
        for j in pomo_jobs:
            ctx.cron_service.remove_job(j.id)
        return f"🍅 Pomodoro parado. {len(pomo_jobs)} timer(s) cancelado(s)."

    # /pomodoro status
    if sub == "status":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return "🍅 Nenhum Pomodoro ativo. Usa /pomodoro para iniciar."
        lines = ["🍅 **Pomodoro(s) ativos:**"]
        for j in pomo_jobs:
            next_ms = j.state.next_run_at_ms if j.state else None
            if next_ms:
                s = int((next_ms - time.time() * 1000) / 1000)
                m = s // 60
                lines.append(f"  • {j.id}: {m} min restantes")
            else:
                lines.append(f"  • {j.id}: agendado")
        return "\n".join(lines)

    # /pomodoro ou /pomodoro start [tarefa]
    if sub and sub != "start":
        arg = rest
    task_label = arg[:30] if arg else "foco"
    message = f"🍅 Pomodoro terminou! 🍅 5 min de pausa. (/pomodoro para próximo)"
    if task_label and task_label != "foco":
        message = f"🍅 Pomodoro «{task_label}» terminou! 🍅 5 min de pausa. (/pomodoro para próximo)"

    # Só um Pomodoro ativo por vez
    jobs = ctx.cron_service.list_jobs(include_disabled=False)
    if any(
        getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        for j in jobs
    ):
        return "🍅 Já tens um Pomodoro ativo. /pomodoro stop para cancelar e iniciar outro."

    try:
        result = await ctx.cron_tool.execute(
            action="add",
            message=message,
            in_seconds=POMODORO_WORK_SEC,
            suggested_prefix="POM",
        )
        if "limite" in (result or "").lower() or "limit" in (result or "").lower():
            return result
        # Formatar resposta com hora de término
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_timezone
            from backend.timezone import format_utc_timestamp_for_user
            db = SessionLocal()
            try:
                tz = get_user_timezone(db, ctx.chat_id)
                end_sec = int(time.time()) + POMODORO_WORK_SEC
                end_str = format_utc_timestamp_for_user(end_sec, tz)
            finally:
                db.close()
        except Exception:
            end_str = "em 25 min"
        return (
            f"🍅 **Pomodoro iniciado!**\n"
            f"25 min de foco. Aviso às {end_str}.\n"
            f"Use /pomodoro stop para cancelar."
        )
    except ValueError as e:
        if "MAX_REMINDERS_EXCEEDED" in str(e):
            from backend.locale import REMINDER_LIMIT_EXCEEDED
            from backend.user_store import get_user_language
            from backend.database import SessionLocal
            try:
                db = SessionLocal()
                lang = get_user_language(db, ctx.chat_id) or "pt-BR"
                db.close()
            except Exception:
                lang = "pt-BR"
            return REMINDER_LIMIT_EXCEEDED.get(lang, REMINDER_LIMIT_EXCEEDED["pt-BR"])
        raise
