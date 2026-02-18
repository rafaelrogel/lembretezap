"""
Lembrete inteligente: sugestões por horário baseadas em histórico, eventos, listas e lembretes.

- Mimo: analisa o contexto (histórico, eventos, listas, cron) e identifica padrões, coisas esquecidas, conexões.
- DeepSeek: cria mensagem curta e amigável com insights personalizados.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from backend.models_db import List, ListItem, Event
from backend.reminder_history import get_reminder_history
from backend.list_history import (
    get_list_items_last_week,
    get_frequent_items,
    format_last_week_for_mimo,
    format_frequent_for_mimo,
)
from backend.user_store import (
    get_or_create_user,
    get_user_language,
    get_user_preferred_name,
    get_user_timezone,
    is_user_in_quiet_window,
)
from backend.timezone import phone_to_default_timezone


_SENT_FILE = Path.home() / ".zapista" / "smart_reminder_sent.json"
_DAILY_USER_MSGS_FILE = Path.home() / ".zapista" / "daily_user_messages.json"

# Mínimo de mensagens que o cliente deve ter enviado no dia (no seu fuso) para receber o lembrete inteligente
SMART_REMINDER_MIN_MESSAGES_FROM_USER = 2


def _today_in_tz(tz_iana: str) -> str:
    """Data de hoje no fuso do utilizador (YYYY-MM-DD)."""
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo(tz_iana)
        return datetime.fromtimestamp(_now_ts, tz=z).strftime("%Y-%m-%d")
    except Exception:
        return datetime.fromtimestamp(_now_ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _load_daily_user_messages() -> dict[str, dict]:
    """Carrega {chat_id: {"date": "YYYY-MM-DD", "count": N}} (data no fuso do user)."""
    import json
    if not _DAILY_USER_MSGS_FILE.exists():
        return {}
    try:
        data = json.loads(_DAILY_USER_MSGS_FILE.read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record_user_message_sent(chat_id: str, tz_iana: str) -> None:
    """Regista que o cliente enviou uma mensagem hoje (no fuso dele). Chamar ao receber cada mensagem."""
    import json
    _DAILY_USER_MSGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = _load_daily_user_messages()
    today = _today_in_tz(tz_iana)
    key = str(chat_id)
    if key not in data or data[key].get("date") != today:
        data[key] = {"date": today, "count": 1}
    else:
        data[key]["count"] = data[key].get("count", 0) + 1
    _DAILY_USER_MSGS_FILE.write_text(json.dumps(data, indent=0))


def get_daily_user_message_count(chat_id: str, tz_iana: str) -> int:
    """Número de mensagens que o cliente enviou hoje (no fuso dele). Só enviar lembrete inteligente se >= SMART_REMINDER_MIN_MESSAGES_FROM_USER."""
    data = _load_daily_user_messages()
    today = _today_in_tz(tz_iana)
    entry = data.get(str(chat_id), {})
    if entry.get("date") != today:
        return 0
    return entry.get("count", 0)


def _load_sent_tracking() -> dict[str, str]:
    """Carrega {chat_id: "YYYY-MM-DD"} de lembretes inteligentes já enviados hoje."""
    import json
    if not _SENT_FILE.exists():
        return {}
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    try:
        data = json.loads(_SENT_FILE.read_text())
        today = datetime.fromtimestamp(_now_ts, tz=timezone.utc).strftime("%Y-%m-%d")
        return {k: v for k, v in (data or {}).items() if v == today}
    except Exception:
        return {}


def _mark_sent_today(chat_id: str) -> None:
    """Marca que enviamos lembrete inteligente hoje a este chat."""
    import json
    _SENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    data[str(chat_id)] = datetime.fromtimestamp(_now_ts, tz=timezone.utc).strftime("%Y-%m-%d")
    _SENT_FILE.write_text(json.dumps(data, indent=0))


def _is_in_smart_reminder_window(tz_iana: str, hour_start: int = 8, hour_end: int = 10) -> bool:
    """True se a hora local do utilizador está na janela (ex.: 8h–10h)."""
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo(tz_iana)
        now_local = datetime.fromtimestamp(_now_ts, tz=z)
        return hour_start <= now_local.hour < hour_end
    except Exception:
        return False


def gather_user_context(
    db: Session,
    chat_id: str,
    cron_jobs: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Reúne contexto do utilizador: lembretes, eventos, listas, cron jobs.
    cron_jobs: lista de CronJob onde payload.to == chat_id (opcional).
    """
    try:
        from zapista.clock_drift import get_effective_time
        _now_ts = get_effective_time()
    except Exception:
        _now_ts = __import__("time").time()

    now = datetime.fromtimestamp(_now_ts, tz=timezone.utc)
    week_ago = now - timedelta(days=7)
    week_ahead = now + timedelta(days=7)

    # Histórico de lembretes (últimos 7 dias)
    reminder_entries = get_reminder_history(db, chat_id, kind=None, limit=50, since=week_ago)
    reminders_summary = []
    for e in reminder_entries[:20]:
        kind = e.get("kind", "")
        msg = (e.get("message") or "")[:80]
        status = e.get("status", "")
        when = e.get("delivered_at") or e.get("schedule_at") or e.get("created_at")
        reminders_summary.append({"kind": kind, "message": msg, "status": status, "when": str(when) if when else ""})

    # Eventos próximos (próximos 7 dias) e recentes
    events_upcoming = []
    events_recent = []
    for ev in db.query(Event).filter(Event.user_id == user.id, Event.deleted.is_(False)).all():
        payload = ev.payload if isinstance(ev.payload, dict) else {}
        nome = (payload.get("nome") or str(ev.payload))[:60]
        data_at = ev.data_at
        if not data_at:
            continue
        try:
            ev_naive = data_at.astimezone(timezone.utc).replace(tzinfo=None) if data_at.tzinfo else data_at
            if not (week_ago <= ev_naive <= week_ahead):
                continue
        except Exception:
            continue
        if ev_naive >= now:
            events_upcoming.append({"nome": nome, "data": str(ev_naive)[:10], "tipo": ev.tipo or "evento"})
        else:
            events_recent.append({"nome": nome, "data": str(ev_naive)[:10], "tipo": ev.tipo or "evento"})

    # Listas com itens pendentes
    lists_with_pending = []
    for lst in db.query(List).filter(List.user_id == user.id).all():
        items = db.query(ListItem).filter(ListItem.list_id == lst.id).all()
        pending = [i.text[:50] for i in items if not i.done]
        done_count = sum(1 for i in items if i.done)
        if pending:
            lists_with_pending.append({
                "name": lst.name,
                "pending": pending[:5],
                "pending_count": len(pending),
                "done_count": done_count,
            })

    # Histórico de listas (semana passada + itens habituais)
    lists_last_week = get_list_items_last_week(db, chat_id, weeks_ago=1)
    lists_frequent = get_frequent_items(db, chat_id, weeks=4, top_per_list=10)

    # Cron jobs do utilizador
    cron_summary = []
    if cron_jobs:
        for j in cron_jobs:
            if getattr(j.payload, "to", None) != chat_id:
                continue
            msg = (getattr(j.payload, "message", None) or j.name or "")[:50]
            nr = getattr(j.state, "next_run_at_ms", None)
            cron_summary.append({"message": msg, "next_run": nr})

    return {
        "reminders_7d": reminders_summary,
        "events_upcoming": events_upcoming,
        "events_recent": events_recent,
        "lists_pending": lists_with_pending,
        "lists_last_week": lists_last_week,
        "lists_frequent": lists_frequent,
        "cron_jobs": cron_summary,
        "now_utc": now.isoformat(),
    }


def _format_context_for_mimo(ctx: dict[str, Any]) -> str:
    """Formata o contexto em texto para o Mimo analisar."""
    parts = []
    if ctx.get("reminders_7d"):
        parts.append("## Lembretes (últimos 7 dias)")
        for r in ctx["reminders_7d"][:15]:
            parts.append(f"- {r['kind']}: {r['message']} (status: {r['status']})")
    if ctx.get("events_upcoming"):
        parts.append("\n## Eventos próximos")
        for e in ctx["events_upcoming"][:10]:
            parts.append(f"- {e['data']}: {e['nome']} ({e['tipo']})")
    if ctx.get("events_recent"):
        parts.append("\n## Eventos recentes (passados)")
        for e in ctx["events_recent"][:5]:
            parts.append(f"- {e['data']}: {e['nome']}")
    if ctx.get("lists_pending"):
        parts.append("\n## Listas com itens por fazer")
        for l in ctx["lists_pending"]:
            parts.append(f"- Lista \"{l['name']}\": {l['pending_count']} pendentes, {l['done_count']} feitos")
            for p in l["pending"][:3]:
                parts.append(f"  · {p}")
    last_week_str = format_last_week_for_mimo(ctx.get("lists_last_week") or {})
    if last_week_str:
        parts.append("\n" + last_week_str)
    frequent_str = format_frequent_for_mimo(ctx.get("lists_frequent") or {})
    if frequent_str:
        parts.append("\n" + frequent_str)
    if ctx.get("cron_jobs"):
        parts.append("\n## Lembretes agendados (cron)")
        for c in ctx["cron_jobs"][:10]:
            parts.append(f"- {c['message']}")
    if not parts:
        return "Sem dados suficientes (histórico, eventos ou listas vazios)."
    return "\n".join(parts)


async def build_smart_reminder_analysis(
    *,
    mimo_provider: Any,
    mimo_model: str,
    context: dict[str, Any],
    user_lang: str,
    preferred_name: str | None,
    local_time_str: str,
) -> str:
    """
    Mimo analisa o contexto e extrai: coisas que o utilizador pode ter esquecido,
    conexões entre lembretes/eventos/listas, sugestões inteligentes.
    """
    if not mimo_provider or not mimo_model:
        return ""
    ctx_text = _format_context_for_mimo(context)
    name = (preferred_name or "").strip() or "utilizador"
    lang_instruction = {
        "pt-PT": "em português de Portugal",
        "pt-BR": "em português do Brasil",
        "es": "en español",
        "en": "in English",
    }.get(user_lang, "in the user's language")

    prompt = (
        f"You are analyzing a user's organization data ({name}). Local time: {local_time_str}. "
        "Based ONLY on the data below, identify:\n"
        "1. Things they may have FORGOTTEN (e.g. reminder delivered days ago with no follow-up, list items long pending, past event with no clear completion)\n"
        "2. SMART CONNECTIONS (e.g. event tomorrow + list 'mercado' has items → suggest buying before the event; recurring reminder + similar past reminder)\n"
        "3. 1-3 SHORT action-oriented suggestions (what to do next, what to check)\n\n"
        "Output a brief analysis (2-4 bullets). Be specific and useful. No generic advice. "
        f"Language: {lang_instruction}. Reply only with the analysis, no preamble.\n\n"
        "Data:\n" + ctx_text
    )
    try:
        r = await mimo_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=mimo_model,
            max_tokens=400,
            temperature=0.4,
        )
        return (r.content or "").strip()
    except Exception as e:
        logger.debug(f"Smart reminder Mimo analysis failed: {e}")
        return ""


async def build_smart_reminder_message(
    *,
    deepseek_provider: Any,
    deepseek_model: str,
    mimo_provider: Any | None = None,
    mimo_model: str | None = None,
    mimo_analysis: str = "",
    user_lang: str = "en",
    preferred_name: str | None = None,
) -> str:
    """
    Mimo primeiro (mais barato) para criar mensagem curta; fallback DeepSeek.
    """
    name = (preferred_name or "").strip() or "utilizador"
    lang_instruction = {
        "pt-PT": "em português de Portugal",
        "pt-BR": "em português do Brasil",
        "es": "en español",
        "en": "in English",
    }.get(user_lang, "in the user's language")

    if not mimo_analysis:
        return f"Olá {name}! ☀️ Tens algo pendente? Diz-me e organizo. 😊"

    prompt = (
        f"Write ONE short, friendly message (1-2 sentences, max 180 chars) to {name} "
        "with smart reminder insights. Use the analysis below. "
        "Be warm, helpful and specific. Include 1 emoji. No bullet points. "
        f"Language: {lang_instruction}. Reply only with the message.\n\n"
        f"Analysis:\n{mimo_analysis}"
    )

    # Mimo primeiro (economiza tokens)
    if mimo_provider and (mimo_model or "").strip():
        try:
            r = await mimo_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=mimo_model or "",
                max_tokens=200,
                temperature=0.6,
            )
            out = (r.content or "").strip().strip('"\'')
            if out and len(out) <= 300:
                return out[:250]
        except Exception as e:
            logger.debug(f"Smart reminder Mimo message failed: {e}")

    # Fallback DeepSeek
    try:
        r = await deepseek_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=deepseek_model,
            max_tokens=200,
            temperature=0.6,
        )
        out = (r.content or "").strip().strip('"\'')
        return out[:250] if out else f"Olá {name}! ☀️ Aqui está o teu lembrete inteligente do dia. 😊"
    except Exception as e:
        logger.debug(f"Smart reminder DeepSeek message failed: {e}")
        return f"Olá {name}! ☀️ Tens algo pendente? Diz-me e organizo. 😊"


async def run_smart_reminder_daily(
    *,
    bus: Any,
    session_manager: Any,
    cron_service: Any,
    deepseek_provider: Any,
    deepseek_model: str,
    mimo_provider: Any | None,
    mimo_model: str | None,
    default_channel: str = "whatsapp",
) -> tuple[int, int]:
    """
    Envia lembrete inteligente a utilizadores na janela horária (8h–10h local).
    Respeita quiet window. Máx 1 por utilizador por dia.
    Retorna (enviados, erros).
    """
    from backend.database import SessionLocal
    from zapista.bus.events import OutboundMessage

    sent = 0
    errors = 0
    sent_today = _load_sent_tracking()

    sessions = session_manager.list_sessions()
    cron_jobs_by_chat: dict[str, list] = {}
    if cron_service:
        for j in cron_service.list_jobs():
            to = getattr(j.payload, "to", None)
            if to:
                cron_jobs_by_chat.setdefault(to, []).append(j)

    for s in sessions:
        key = s.get("key") or ""
        if ":" not in key:
            continue
        channel, chat_id = key.split(":", 1)
        if not chat_id or chat_id in sent_today:
            continue
        ch = channel if channel else default_channel
        if ch != "whatsapp":
            continue

        try:
            db = SessionLocal()
            try:
                if is_user_in_quiet_window(chat_id):
                    continue
                tz_iana = get_user_timezone(db, chat_id) or phone_to_default_timezone(chat_id)
                if not _is_in_smart_reminder_window(tz_iana):
                    continue
                # Só enviar se o cliente já enviou pelo menos N mensagens hoje (proteção anti-spam)
                if get_daily_user_message_count(chat_id, tz_iana) < SMART_REMINDER_MIN_MESSAGES_FROM_USER:
                    continue
                user_lang = get_user_language(db, chat_id)
                preferred_name = get_user_preferred_name(db, chat_id)
                context = gather_user_context(db, chat_id, cron_jobs=cron_jobs_by_chat.get(chat_id, []))
                now_local = datetime.now()
                try:
                    from zoneinfo import ZoneInfo
                    z = ZoneInfo(tz_iana)
                    now_local = datetime.now(z)
                except Exception:
                    pass
                local_time_str = now_local.strftime("%Y-%m-%d %H:%M")
            finally:
                db.close()

            mimo_analysis = await build_smart_reminder_analysis(
                mimo_provider=mimo_provider or deepseek_provider,
                mimo_model=mimo_model or deepseek_model or "",
                context=context,
                user_lang=user_lang,
                preferred_name=preferred_name,
                local_time_str=local_time_str,
            )

            content = await build_smart_reminder_message(
                deepseek_provider=deepseek_provider,
                deepseek_model=deepseek_model or "",
                mimo_provider=mimo_provider,
                mimo_model=mimo_model or "",
                mimo_analysis=mimo_analysis,
                user_lang=user_lang,
                preferred_name=preferred_name,
            )

            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=chat_id,
                content=content,
                metadata={"priority": "high"},
            ))
            _mark_sent_today(chat_id)
            sent += 1
            logger.info(f"Smart reminder sent to {chat_id[:20]}...")
        except Exception as e:
            errors += 1
            logger.warning(f"Smart reminder failed for {key}: {e}")

    return sent, errors
