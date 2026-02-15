"""Handler Pomodoro: técnica 25 min foco + 5 min pausa. Aceita /pomodoro e linguagem natural (texto/áudio)."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

POMODORO_WORK_MIN = 25
POMODORO_WORK_SEC = POMODORO_WORK_MIN * 60

# Padrões de linguagem natural para iniciar pomodoro (texto ou transcrição de áudio)
_NL_POMODORO_START = re.compile(
    r"\b(abre?|abrir|inicia|iniciar|come[çc]a|come[çc]ar|carrega|carregar|ativa|ativar|quero|start|open|begin)\b.*\bpomodoro\b|"
    r"\bpomodoro\b.*\b(agora|por\s+favor|pf)\b|^\s*pomodoro\s*$",
    re.I,
)
# Evitar confundir com lembrete futuro: "lembra de fazer pomodoro amanhã"
_NL_POMODORO_FUTURE_TIME = re.compile(
    r"\b(amanh[ãa]|depois|em\s+\d+|às\s+\d|à\s+\d|próxima|semana|amanhã|tomorrow|next)\b",
    re.I,
)


def _is_nl_pomodoro_start(content: str) -> bool:
    """True se a mensagem em texto/áudio pede para iniciar pomodoro agora (sem tempo futuro)."""
    if not content or len(content.strip()) > 120:
        return False
    t = content.strip()
    if "pomodoro" not in t.lower():
        return False
    if _NL_POMODORO_FUTURE_TIME.search(t):
        return False
    return bool(_NL_POMODORO_START.search(t)) or t.lower().strip() == "pomodoro"


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
    Também aceita linguagem natural: "abre um pomodoro", "pomodoro por favor", "inicia o pomodoro agora", etc.
    """
    t = (content or "").strip()
    is_nl = _is_nl_pomodoro_start(t)
    if not t.lower().startswith("/pomodoro") and not is_nl:
        return None

    if is_nl:
        rest = ""
    else:
        rest = t[9:].strip()  # após "/pomodoro"
    sub = (rest.split(None, 1)[0] if rest else "").lower()
    arg = rest.split(None, 1)[1].strip() if rest and len(rest.split(None, 1)) > 1 else ""

    if not ctx.cron_service or not ctx.cron_tool:
        return "🍅 Pomodoro: o cron não está disponível neste canal. 🍅"

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id)

    # /pomodoro stop
    if sub == "stop":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return "🍅 Nenhum Pomodoro ativo. 🍅"
        for j in pomo_jobs:
            ctx.cron_service.remove_job(j.id)
        return f"🍅 Pomodoro parado. {len(pomo_jobs)} timer(s) cancelado(s). 🍅"

    # /pomodoro status
    if sub == "status":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return "🍅 Nenhum Pomodoro ativo. Usa /pomodoro para iniciar. 🍅"
        lines = ["🍅 **Pomodoro(s) ativos:**"]
        for j in pomo_jobs:
            next_ms = j.state.next_run_at_ms if j.state else None
            if next_ms:
                s = int((next_ms - time.time() * 1000) / 1000)
                m = s // 60
                lines.append(f"  • {j.id}: {m} min restantes")
            else:
                lines.append(f"  • {j.id}: agendado")
        return "\n".join(lines) + " 🍅"

    # /pomodoro ou /pomodoro start [tarefa]
    if sub and sub != "start":
        arg = rest
    task_label = arg[:30] if arg else "foco"
    message = f"🍅 Pomodoro terminou! 5 min de pausa. (/pomodoro para próximo) 🍅"
    if task_label and task_label != "foco":
        message = f"🍅 Pomodoro «{task_label}» terminou! 5 min de pausa. (/pomodoro para próximo) 🍅"

    # Só um Pomodoro ativo por vez
    jobs = ctx.cron_service.list_jobs(include_disabled=False)
    if any(
        getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        for j in jobs
    ):
        return "🍅 Já tens um Pomodoro ativo. /pomodoro stop para cancelar e iniciar outro. 🍅"

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
            f"Use /pomodoro stop para cancelar. 🍅"
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
            msg = REMINDER_LIMIT_EXCEEDED.get(lang, REMINDER_LIMIT_EXCEEDED["pt-BR"])
            return f"🍅 {msg} 🍅" if msg else None
        raise
