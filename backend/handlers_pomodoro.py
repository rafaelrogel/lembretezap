"""Handler Pomodoro: técnica 25 min foco + 5 min pausa. Aceita /pomodoro e linguagem natural (texto/áudio)."""

from __future__ import annotations

import re
import time
from zapista.clock_drift import get_effective_time, get_effective_time_ms
from typing import TYPE_CHECKING
from backend.database import SessionLocal
from backend.user_store import get_user_language
from backend.locale import (
    POMODORO_INFO, POMODORO_UNAVAILABLE, POMODORO_NONE_ACTIVE, POMODORO_STOPPED,
    POMODORO_STATUS_HEADER, POMODORO_FINISHED, POMODORO_FINISHED_TASK,
    POMODORO_ALREADY_ACTIVE, POMODORO_START_MSG
)

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext

POMODORO_WORK_MIN = 25
POMODORO_WORK_SEC = POMODORO_WORK_MIN * 60

# Padrões de linguagem natural para iniciar pomodoro (texto ou transcrição de áudio)
_NL_POMODORO_START = re.compile(
    r"\b(abre?|abrir|inicia|iniciar|come[çc]a|come[çc]ar|carrega|carregar|ativ[ae][rm]?|p[õo]e|quero|start|open|begin)\b.*\bpomodoro\b|"
    r"\bpomodoro\b.*\b(agora|por\s+favor|pf)\b|^\s*pomodoro\s*$",
    re.I,
)
# Padrão para saber se tem pomodoro ou o que é
_NL_POMODORO_INFO = re.compile(
    r"\b(voc[êe]|tu)\b.*\b(tem|tens)\b.*\bpomodoro\b|"
    r"\bo\s+que\s+[ée]\s+pomodoro\b|\bexplica\s+pomodoro\b",
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
    t = content.strip().lower()
    if "pomodoro" not in t:
        return False
    if _NL_POMODORO_FUTURE_TIME.search(t):
        return False
        
    # Evitar intercetar mensagens de multi-intenção, deixando o LLM processá-las
    multi_intent_words = (
        " e ", " and ", " y ", " também ", " also ", " también ",
        " adiciona", " add ", " añade", " agenda", " lembra", " remind ", " recuerda ", 
        " lista", " list ", " cria ", " create ", " apaga ", " remove ", " delete "
    )
    t_padded = f" {t} "
    if any(word in t_padded for word in multi_intent_words):
        return False
        
    return bool(_NL_POMODORO_START.search(t)) or t.strip() == "pomodoro"


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
    is_info = _NL_POMODORO_INFO.search(t)
    
    if not t.lower().startswith("/pomodoro") and not is_nl and not is_info:
        return None

    db = SessionLocal()
    try:
        lang = get_user_language(db, ctx.chat_id, ctx.phone_for_locale) or "pt-BR"
    finally:
        db.close()

    if is_info:
        return POMODORO_INFO.get(lang, POMODORO_INFO["pt-BR"])

    if is_nl:
        rest = ""
    else:
        rest = t[9:].strip()  # após "/pomodoro"
    sub = (rest.split(None, 1)[0] if rest else "").lower()
    arg = rest.split(None, 1)[1].strip() if rest and len(rest.split(None, 1)) > 1 else ""

    if not ctx.cron_service or not ctx.cron_tool:
        from backend.locale import POMODORO_UNAVAILABLE
        return POMODORO_UNAVAILABLE.get(lang, POMODORO_UNAVAILABLE["en"])

    ctx.cron_tool.set_context(ctx.channel, ctx.chat_id, ctx.phone_for_locale)

    # /pomodoro stop
    if sub == "stop":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return POMODORO_NONE_ACTIVE.get(lang, POMODORO_NONE_ACTIVE["pt-BR"]).replace(" Usa /pomodoro para iniciar.", "").replace(" Use /pomodoro para iniciar.", "").replace(" Usa /pomodoro para iniciar.", "").replace(" Use /pomodoro to start.", "")
        for j in pomo_jobs:
            ctx.cron_service.remove_job(j.id)
        from backend.locale import POMODORO_STOPPED
        return POMODORO_STOPPED.get(lang, POMODORO_STOPPED["en"]).format(count=len(pomo_jobs))

    # /pomodoro status
    if sub == "status":
        jobs = ctx.cron_service.list_jobs(include_disabled=False)
        pomo_jobs = [
            j for j in jobs
            if getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        ]
        if not pomo_jobs:
            return POMODORO_NONE_ACTIVE.get(lang, POMODORO_NONE_ACTIVE["pt-BR"])
        lines = [POMODORO_STATUS_HEADER.get(lang, POMODORO_STATUS_HEADER["pt-BR"])]
        for j in pomo_jobs:
            next_ms = j.state.next_run_at_ms if j.state else None
            if next_ms:
                s = int((next_ms - get_effective_time_ms()) / 1000)
                m = s // 60
                from backend.locale import POMODORO_TIME_REMAINING
                label = POMODORO_TIME_REMAINING.get(lang, POMODORO_TIME_REMAINING["en"]).format(min=m)
                lines.append(f"  • {j.id}: {label}")
            else:
                from backend.locale import POMODORO_SCHEDULED
                label = POMODORO_SCHEDULED.get(lang, POMODORO_SCHEDULED["en"])
                lines.append(f"  • {j.id}: {label}")
        return "\n".join(lines) + " 🍅"

    # /pomodoro ou /pomodoro start [tarefa]
    if sub and sub != "start":
        arg = rest
    task_label = arg[:30] if arg else "foco"
    if task_label and task_label != "foco":
        message = POMODORO_FINISHED_TASK.get(lang, POMODORO_FINISHED_TASK["pt-BR"]).format(task=task_label)
    else:
        message = POMODORO_FINISHED.get(lang, POMODORO_FINISHED["pt-BR"])

    # Só um Pomodoro ativo por vez
    jobs = ctx.cron_service.list_jobs(include_disabled=False)
    if any(
        getattr(j.payload, "to", None) == ctx.chat_id and _is_pomodoro_job(j)
        for j in jobs
    ):
        msg = POMODORO_ALREADY_ACTIVE.get(lang, POMODORO_ALREADY_ACTIVE["pt-BR"])
        return f"🍅 {msg} 🍅"

    try:
        result = await ctx.cron_tool.execute(
            action="add",
            message=message,
            in_seconds=POMODORO_WORK_SEC,
            suggested_prefix="POM",
            pomodoro_cycle=1,
            pomodoro_phase="focus",
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
                tz = get_user_timezone(db, ctx.chat_id, ctx.phone_for_locale)
                end_sec = int(get_effective_time()) + POMODORO_WORK_SEC
                end_str = format_utc_timestamp_for_user(end_sec, tz)
            finally:
                db.close()
        except Exception:
            end_str = "em 25 min"
        
        template = POMODORO_START_MSG.get(lang, POMODORO_START_MSG["pt-BR"])
        return template.format(cycle=1, end_time=end_str)
    except ValueError as e:
        if "MAX_REMINDERS_EXCEEDED" in str(e):
            from backend.locale import REMINDER_LIMIT_EXCEEDED
            msg = REMINDER_LIMIT_EXCEEDED.get(lang, REMINDER_LIMIT_EXCEEDED["pt-BR"])
            return f"🍅 {msg} 🍅" if msg else None
        raise
