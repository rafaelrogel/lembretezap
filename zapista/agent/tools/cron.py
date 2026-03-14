"""Cron tool for scheduling reminders and tasks."""

import time
from typing import Any, TYPE_CHECKING

from loguru import logger
from zapista.agent.tools.base import Tool

def _effective_now_ms() -> int:
    """Agora em ms (UTC); usa correção de clock_drift se houver desvio grande."""
    try:
        from zapista.clock_drift import get_effective_time_ms
        return get_effective_time_ms()
    except Exception:
        return int(time.time() * 1000)
from zapista.cron.service import CronService
from zapista.cron.types import CronSchedule
from zapista.cron.friendly_id import get_prefix_from_list
from backend.sanitize import sanitize_string, validate_cron_expr, MAX_MESSAGE_LEN

if TYPE_CHECKING:
    from zapista.providers.base import LLMProvider


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""

    def __init__(
        self,
        cron_service: CronService,
        scope_provider: "LLMProvider | None" = None,
        scope_model: str = "",
        session_manager: Any = None,
    ):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._phone_for_locale: str | None = None
        self._scope_provider = scope_provider
        self._scope_model = (scope_model or "").strip()
        self._session_manager = session_manager
        self._audio_mode: bool = False
    
    def set_context(self, channel: str, chat_id: str, phone_for_locale: str | None = None) -> None:
        """Set the current session context for delivery. phone_for_locale: número para inferir idioma na entrega (quando chat_id é LID)."""
        self._channel = channel
        self._chat_id = chat_id
        self._phone_for_locale = phone_for_locale

    def set_allow_relaxed_interval(self, allow: bool) -> None:
        """Para este turno: cliente insistiu, permitir intervalo até 30 min."""
        self._allow_relaxed_interval = allow

    def set_audio_mode(self, audio_mode: bool) -> None:
        """Para este turno: entregar lembretes como áudio TTS."""
        self._audio_mode = audio_mode

    def _get_allow_relaxed(self, explicit: bool | None = None) -> bool:
        return explicit if explicit is not None else getattr(self, "_allow_relaxed_interval", False)

    def _get_user_lang(self) -> str:
        """Idioma do usuário para mensagens (pt-PT, pt-BR, es, en). Usa preferência guardada; senão infere pelo número."""
        if not self._chat_id:
            return "pt-BR"
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language
            from backend.locale import resolve_response_language
            db = SessionLocal()
            try:
                lang = get_user_language(db, self._chat_id, getattr(self, "_phone_for_locale", None)) or "pt-BR"
                return resolve_response_language(lang, self._chat_id, getattr(self, "_phone_for_locale", None))
            finally:
                db.close()
        except Exception:
            return "pt-BR"
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return (
            "Schedule one-time or recurring reminders. Actions: add, list, remove. "
            "CRITICAL — CALENDAR QUERIES: Whenever the user asks about their reminders, calendar, agenda, tasks, "
            "'lembretes', 'compromissos', 'o que tenho hoje/amanhã', 'minha agenda', 'quais lembretes', or ANY similar phrasing "
            "in ANY language, you MUST call this tool with action='list'. "
            "NEVER answer calendar/reminder questions from session history, memory, or conversation context. "
            "Session history may contain DELIVERED (already sent and deleted) reminders that no longer exist. "
            "Only the tool response reflects the true current state. "
            "message = WHAT to remind (e.g. 'ir à farmácia', 'tomar remédio') — required. Never 'lembrete' or 'alerta'. "
            "CRITICAL: NEVER invent or assume a time. If the user did not explicitly say a time/date (e.g. '10h', 'amanhã', 'daqui a 5 min'), "
            "you MUST ask 'Para quando?' BEFORE calling this tool. Do NOT default to '10h', 'amanhã', 'esta tarde' or any arbitrary time. "
            "If user says 'lembrete amanhã 10h' without event, ask 'De que é o lembrete?' first. "
            "For add: CRITICAL: DO NOT CALCULATE TIME. Parsing is done by the system. "
            "ALWAYS pass the exact time text from the user in 'time_input' (e.g. 'daqui a 5 min', 'amanhã 9h'). "
            "IGNORE 'in_seconds' and 'target_at_iso' unless explicitly constructing a machine-generated timestamp. "
            "System will interpret 'time_input' in the User's Timezone. "
            "every_seconds = repeat; cron_expr = fixed times (interpreted in user timezone when stored). "
            "BULK DELETE: if user says 'delete all', 'cancel all reminders', 'remove all my reminders' or equivalent, "
            "use action='remove_all' (no job_id needed). "
            "SINGLE DELETE: call action='list' first to get IDs, then action='remove' with the correct job_id. "
            "IMPORTANT: when the user lists multiple reminders in one message (e.g. 'lembre X em 6 min, depois Y em 7 min, depois Z'), "
            "register each one as a FULLY INDEPENDENT reminder with its own time_input. NEVER chain them with depends_on_job_id. "
            "depends_on_job_id is ONLY for when the user explicitly says 'só me lembra de B depois de eu confirmar A com 👍' or equivalent. "
            "When confirming a reminder to the user, use the EXACT time from this tool's return (e.g. 'Será enviado às HH:MM'); never substitute with the Current Time from the prompt."
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "remove_all", "pomodoro"],
                    "description": "Action: add, list, remove (one job_id), remove_all (delete ALL reminders of this user), or pomodoro (start a 25-min focus cycle)"
                },
                "message": {
                    "type": "string",
                    "description": "What to remind (required). Must describe the EVENT/ACTION, e.g. 'ir à farmácia', 'tomar remédio', 'reunião com João'. NEVER use 'lembrete' or 'alerta' as message — that's the type. If user says 'lembrete amanhã 10h' without specifying the event, do NOT create; instead ask 'De que é o lembrete?' with examples."
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Repeat every N seconds (minimum 1800 = 30 min, e.g. 3600 = hourly)"
                },
                "target_at_iso": {
                    "type": "string",
                    "description": "DEPRECATED / INTERNAL USE ONLY. Do not use. System calculates this."
                },
                "time_input": {
                    "type": "string",
                    "description": "REQUIRED. The exact time text from the user (e.g. 'daqui a 5 minutos', 'amanhã às 10h', 'toda terça'). System will parse this using backend logic/timezone. ALWAYS USE THIS for natural language times."
                },
                "in_seconds": {
                    "type": "integer",
                    "description": "DEPRECATED / INTERNAL USE ONLY. Do not use. System calculates this."
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression for fixed times (e.g. '0 9 * * *' = daily at 9h)"
                },
                "start_date": {
                    "type": "string",
                    "description": "Recurring only: start date ISO YYYY-MM-DD. Reminders will NOT fire before this date (e.g. '2026-07-01' for 'a partir de 1º de julho')"
                },
                "end_date": {
                    "type": "string",
                    "description": "Recurring only: end date ISO YYYY-MM-DD. Reminders will stop after this date (e.g. '2026-12-31' for 'até fim do ano')"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
                },
                "remind_again_if_unconfirmed_seconds": {
                    "type": "integer",
                    "description": "If set (e.g. 600 = 10 min), re-sends the reminder after this many seconds if user does not react 👍. Use when user says 'lembra de novo em X min se eu não confirmar'."
                },
                "depends_on_job_id": {
                    "type": "string",
                    "description": "ONLY use this when user EXPLICITLY says something like 'só me lembra de B depois de eu marcar A como feito' or 'quando eu confirmar A com 👍, avisa para B'. Do NOT use for multi-reminder messages where user says 'depois' as a time reference (e.g. 'lembra X em 6 min, depois Y em 7 min') — in those cases, create each reminder independently."
                },
                "has_deadline": {
                    "type": "boolean",
                    "description": "If true: 'até X' = if not done by X, alert + remind 3x; no response = remove. Use when user says 'lembra até amanhã 18h' or 'se não fizer até X, alerta'."
                },
                "suggested_draft": {
                    "type": "string",
                    "description": "A draft message for the user to send/forward. Use this when the reminder is about sending a message (e.g., birthday, holiday). The draft will be delivered as a separate message alongside the reminder."
                }
            },
            "required": ["action"]
        }
    
    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        in_seconds: int | None = None,
        target_at_iso: str | None = None,
        time_input: str | None = None,
        cron_expr: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        job_id: str | None = None,
        allow_relaxed_interval: bool = False,
        remind_again_if_unconfirmed_seconds: int | None = None,
        depends_on_job_id: str | None = None,
        has_deadline: bool = False,
        suggested_draft: str | None = None,
        **kwargs: Any
    ) -> str:
        logger.info(f"CronTool.execute inputs: action={action}, msg={message}, time_input={time_input}, target={target_at_iso}, in_seconds={in_seconds}, every={every_seconds}, cron={cron_expr}, chat_id={self._chat_id}, channel={self._channel}")

        if action == "list":
            return self._list_jobs()
        if action == "remove":
            return self._remove_job(job_id)
        if action == "remove_all":
            return self._remove_all_jobs()
            
        if action == "pomodoro":
            from backend.locale import POMODORO_FINISHED_TASK, POMODORO_FINISHED
            _lang = self._get_user_lang()
            if message:
                msg = POMODORO_FINISHED_TASK.get(_lang, POMODORO_FINISHED_TASK["pt-BR"]).format(task=message[:30])
            else:
                msg = POMODORO_FINISHED.get(_lang, POMODORO_FINISHED["pt-BR"])
                
            return await self._add_job(
                message=msg,
                every_seconds=None,
                in_seconds=25 * 60,
                cron_expr=None,
                target_at_iso=None,
                start_date=None,
                end_date=None,
                suggested_prefix="POM",
                use_pre_reminders=False,
                long_event_24h=False,
                allow_relaxed_interval=True,
                remind_again_if_unconfirmed_seconds=None,
                depends_on_job_id=None,
                has_deadline=False,
                suggested_draft=None,
                audio_mode=False,
                pomodoro_cycle=1,
                pomodoro_phase="focus",
            )

        if action == "add":
            # Phase 2: System-side time parsing via backend.time_parse
            if time_input:
                try:
                    from backend.time_parse import parse_lembrete_time
                    from backend.database import SessionLocal
                    from backend.user_store import get_user_timezone
                    from backend.timezone import phone_to_default_timezone

                    tz_iana = "UTC"
                    db = SessionLocal()
                    try:
                        tz_iana = get_user_timezone(db, self._chat_id, self._phone_for_locale) or phone_to_default_timezone(self._phone_for_locale or self._chat_id) or "UTC"
                    finally:
                        db.close()
                    
                    parsed = parse_lembrete_time(time_input, tz_iana=tz_iana)
                    if parsed:
                        if parsed.get("in_seconds"):
                            in_seconds = parsed["in_seconds"]
                            # clear conflicting args if parsing succeeded
                            target_at_iso = None
                        elif parsed.get("cron_expr"):
                            cron_expr = parsed["cron_expr"]
                            every_seconds = None
                            in_seconds = None
                            target_at_iso = None
                        elif parsed.get("every_seconds"):
                            every_seconds = parsed["every_seconds"]
                            cron_expr = None
                            in_seconds = None
                            target_at_iso = None
                        
                        # parsed['message'] usually contains the text sans time.
                        # If the LLM passed a generic 'Lembrete' or empty message, use the parsed one.
                        # If LLM passed a specific message (e.g. 'Tomar chá'), keep it (unless it's just 'Lembrete').
                        parsed_msg = parsed.get("message")
                        if parsed_msg and (not message or message.lower().strip() in ("lembrete", "alerta", "aviso")):
                            message = parsed_msg
                        
                        logger.info(f"CronTool extracted from time_input='{time_input}': in_s={in_seconds}, cron={cron_expr}, every={every_seconds}, msg='{message}'")
                    else:
                        # Parsing returned None or empty dict
                        logger.warning(f"CronTool: time_input='{time_input}' parsed to empty/None. Failing.")
                        return f"Error: Could not parse time from '{time_input}'. Please use standard format like 'daqui a 5 minutos', 'amanhã 9h', 'toda terça'."
                    
                    # VALIDATION: If we have time_input, we MUST have extracted a schedule.
                    if in_seconds is None and cron_expr is None and every_seconds is None and target_at_iso is None:
                         logger.warning(f"CronTool: time_input='{time_input}' yielded no schedule. Returns: {parsed}")
                         return f"Error: Could not extract time/schedule from '{time_input}'. Ensure it contains a time expression."

                except Exception as e:
                    logger.error(f"CronTool failed to parse time_input '{time_input}': {e}")
                    return f"Error parsing time_input: {e}"

            from backend.guardrails import is_absurd_request
            allow_relaxed = allow_relaxed_interval or self._get_allow_relaxed()
            absurd = is_absurd_request(message, allow_relaxed=allow_relaxed)
            if absurd:
                return absurd
            prefix = get_prefix_from_list(message or "")
            if prefix is None and self._scope_provider and self._scope_model:
                prefix = await self._ask_mimo_abbreviation(message or "")
            use_pre_reminders = True
            long_event_24h = False
            if in_seconds is not None and in_seconds > 0:
                from backend.reminder_lead_classifier import needs_advance_alert, is_long_duration
                long_event_24h = is_long_duration(in_seconds)
                use_pre_reminders = long_event_24h or await needs_advance_alert(
                    message or "", in_seconds, self._scope_provider, self._scope_model
                )
            return await self._add_job(
                message, every_seconds, in_seconds, cron_expr,
                target_at_iso=target_at_iso,
                start_date=start_date,
                end_date=end_date,
                suggested_prefix=prefix,
                use_pre_reminders=use_pre_reminders,
                long_event_24h=long_event_24h,
                allow_relaxed_interval=allow_relaxed,
                remind_again_if_unconfirmed_seconds=remind_again_if_unconfirmed_seconds,
                depends_on_job_id=depends_on_job_id,
                has_deadline=has_deadline,
                suggested_draft=suggested_draft,
                audio_mode=getattr(self, "_audio_mode", False),
                pomodoro_cycle=kwargs.get("pomodoro_cycle"),
                pomodoro_phase=kwargs.get("pomodoro_phase"),
                is_important=use_pre_reminders and in_seconds is not None and in_seconds > 0,
            )
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"
    
    async def _ask_mimo_abbreviation(self, message: str) -> str | None:
        """Pede ao Xiaomi MIMO 2–3 letras para o ID do lembrete quando a mensagem não está na lista de palavras."""
        if not message or not self._scope_provider or not self._scope_model:
            return None
        try:
            prompt = (
                f"The user created a reminder: «{message[:200]}». "
                "Reply with ONLY 2 or 3 uppercase letters to use as a short ID (e.g. AL for lunch, EN for delivery). "
                "No explanation, no punctuation. Only the letters."
            )
            r = await self._scope_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self._scope_model,
                max_tokens=10,
                temperature=0,
            )
            raw = (r.content or "").strip().upper()
            letters = "".join(c for c in raw if c.isalpha())[:3]
            return letters if len(letters) >= 2 else None
        except Exception:
            return None

    def _schedule_matches(self, existing_schedule: CronSchedule, new_schedule: CronSchedule) -> bool:
        """True se o schedule existente corresponde ao novo (mesmo tipo e parâmetros)."""
        if existing_schedule.kind != new_schedule.kind:
            return False
        if new_schedule.kind == "every":
            return existing_schedule.every_ms == new_schedule.every_ms
        if new_schedule.kind == "cron":
            return (existing_schedule.expr or "").strip() == (new_schedule.expr or "").strip()
        if new_schedule.kind == "at":
            return existing_schedule.at_ms == new_schedule.at_ms
        return False

    async def _check_duplicate_with_context(
        self,
        message: str,
        schedule: CronSchedule,
    ) -> str | None:
        """
        Verifica duplicatas: exact match → "Já está registado".
        Mesmo schedule mas mensagem diferente → Mimo decide com últimas 20 msgs.
        Retorna mensagem a enviar se for duplicata, None para proseguir.
        """
        msg_norm = (message or "").lower().strip()
        existing_jobs = [
            j for j in self._cron.list_jobs(include_disabled=True)
            if getattr(j.payload, "to", None) == self._chat_id
            and j.enabled
            and self._schedule_matches(j.schedule, schedule)
        ]
        if not existing_jobs:
            return None

        for existing in existing_jobs:
            existing_msg = (existing.payload.message or "").lower().strip()
            if existing_msg == msg_norm:
                return f"Este lembrete já está registado. (id: {existing.id})"

        # Mensagem diferente, mesmo schedule: Mimo decide com contexto
        if not self._scope_provider or not self._scope_model or not self._session_manager:
            return None  # sem Mimo → criar (cliente não fica na mão)

        history_text = ""
        try:
            session_key = f"{self._channel}:{self._chat_id}"
            session = self._session_manager.get_or_create(session_key)
            history = (session.messages or [])[-20:]
            history_text = "\n".join(
                f"{m.get('role', '?')}: {(m.get('content') or '')[:150]}"
                for m in history
            )
        except Exception:
            return None

        for existing in existing_jobs:
            existing_msg = (existing.payload.message or "").strip()
            if existing_msg.lower() == msg_norm:
                continue
            try:
                prompt = (
                    f"Conversa recente:\n{history_text[-2000:]}\n\n"
                    f"Usuário quer criar lembrete: «{message[:200]}»\n"
                    f"Já existe lembrete: «{existing_msg[:200]}»\n\n"
                    "O novo lembrete é o MESMO que o existente? (ex: mesmo remédio, mesma tarefa, mesmo compromisso)\n"
                    "Responde APENAS: SIM ou NAO"
                )
                r = await self._scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=self._scope_model,
                    max_tokens=10,
                    temperature=0,
                )
                raw = (r.content or "").strip().upper()
                if "SIM" in raw or raw.startswith("S"):
                    return f"Este lembrete já está registado. (id: {existing.id})"
            except Exception:
                pass  # em caso de erro, criar (cliente não fica na mão)
        return None

    async def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        in_seconds: int | None,
        cron_expr: str | None,
        target_at_iso: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        suggested_prefix: str | None = None,
        use_pre_reminders: bool = True,
        long_event_24h: bool = False,
        allow_relaxed_interval: bool = False,
        remind_again_if_unconfirmed_seconds: int | None = None,
        depends_on_job_id: str | None = None,
        has_deadline: bool = False,
        suggested_draft: str | None = None,
        audio_mode: bool = False,
        pomodoro_cycle: int | None = None,
        pomodoro_phase: str | None = None,
        is_important: bool = False,
    ) -> str:
        message = sanitize_string(message or "", MAX_MESSAGE_LEN)
        if not message:
            return "Error: message is required for add"
        # Mensagem vaga (ex.: "lembrete amanhã 10h" sem dizer o quê) → pedir esclarecimento
        from backend.guardrails import is_vague_reminder_message
        from backend.locale import REMINDER_ASK_WHAT
        if is_vague_reminder_message(message):
            _lang = self._get_user_lang()
            return REMINDER_ASK_WHAT.get(_lang, REMINDER_ASK_WHAT["pt-BR"])
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if cron_expr and not validate_cron_expr(cron_expr):
            return "Error: expressão cron inválida (use 5 campos: min hora dia mês dia-semana)"
        if cron_expr:
            from backend.guardrails import is_cron_interval_too_short
            from backend.locale import REMINDER_MIN_INTERVAL_2H
            _lang = self._get_user_lang()
            if is_cron_interval_too_short(cron_expr, allow_relaxed=allow_relaxed_interval):
                return REMINDER_MIN_INTERVAL_2H.get(_lang, REMINDER_MIN_INTERVAL_2H["pt-BR"])
        if in_seconds is not None and in_seconds <= 0:
            _lang = self._get_user_lang()
            from backend.locale import REMINDER_TIME_PAST_TODAY
            return REMINDER_TIME_PAST_TODAY.get(_lang, REMINDER_TIME_PAST_TODAY["pt-BR"])
        if in_seconds is not None and in_seconds > 86400 * 365:
            return "Error: in_seconds deve estar entre 0 e 1 ano"
        min_every = 1800 if allow_relaxed_interval else 7200  # 30 min ou 2h
        if every_seconds is not None and (every_seconds < min_every or every_seconds > 86400 * 30):
            from backend.locale import REMINDER_MIN_INTERVAL_30MIN, REMINDER_MIN_INTERVAL_2H
            _lang = self._get_user_lang()
            msg_map = REMINDER_MIN_INTERVAL_30MIN if allow_relaxed_interval else REMINDER_MIN_INTERVAL_2H
            return msg_map.get(_lang, msg_map["pt-BR"])

        # Parse start_date (YYYY-MM-DD) → not_before_ms para recorrentes ("a partir de 1º julho")
        not_before_ms: int | None = None
        if start_date and (every_seconds or cron_expr):
            try:
                from datetime import datetime, timezone
                dt = datetime.strptime(start_date.strip()[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
                not_before_ms = int(dt.timestamp() * 1000)
            except (ValueError, TypeError):
                pass
        # Parse end_date (YYYY-MM-DD) ou ms → not_after_ms para recorrentes ("até fim do ano")
        not_after_ms: int | None = None
        if end_date and (every_seconds or cron_expr):
            if isinstance(end_date, (int, float)) and end_date > 0:
                not_after_ms = int(end_date)
            else:
                try:
                    from datetime import datetime, timezone
                    dt = datetime.strptime(str(end_date).strip()[:10], "%Y-%m-%d").replace(
                        hour=23, minute=59, second=59, microsecond=999
                    ).replace(tzinfo=timezone.utc)
                    not_after_ms = int(dt.timestamp() * 1000)
                except (ValueError, TypeError):
                    pass
        # Pontual (não recorrente): após a entrega o job é removido do cron (esquecido pelo sistema); pode existir histórico noutra camada
        if (target_at_iso or (in_seconds is not None and in_seconds > 0)):
            if target_at_iso:
                # Interpret ISO string in user's timezone
                try:
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    from backend.database import SessionLocal
                    from backend.user_store import get_user_timezone
                    from backend.timezone import phone_to_default_timezone
                    
                    db = SessionLocal()
                    try:
                        tz_name = get_user_timezone(db, self._chat_id, self._phone_for_locale) or phone_to_default_timezone(self._phone_for_locale or self._chat_id) or "UTC"
                    finally:
                        db.close()
                    
                    tz = ZoneInfo(tz_name)
                    # "2025-02-19 14:30:00" -> naive
                    dt_naive = datetime.fromisoformat(target_at_iso.replace("Z", ""))
                    if dt_naive.tzinfo is None:
                        dt_local = dt_naive.replace(tzinfo=tz)
                    else:
                        dt_local = dt_naive.astimezone(tz)
                    
                    at_ms = int(dt_local.timestamp() * 1000)
                    
                    # Update in_seconds for later logic (deadlines, pre-reminders)
                    now_ms = _effective_now_ms()
                    in_seconds = (at_ms - now_ms) // 1000
                except Exception as e:
                    logger.error(f"Failed to parse target_at_iso '{target_at_iso}': {e}")
                    return f"Error parsing time: {target_at_iso}. Use format YYYY-MM-DD HH:MM:SS"
            else:
                now_ms = _effective_now_ms()
                at_ms = now_ms + in_seconds * 1000

            if at_ms <= _effective_now_ms():
                now_ms = _effective_now_ms()
                delta_past_ms = now_ms - at_ms
                if delta_past_ms > 300_000:  # Aumentado para 5 minutos para maior robustez
                    logger.warning(f"Cron: rejecting reminder {delta_past_ms/1000}s in the past")
                    from backend.locale import REMINDER_TIME_PAST_TODAY
                    _lang = self._get_user_lang()
                    return REMINDER_TIME_PAST_TODAY.get(_lang, REMINDER_TIME_PAST_TODAY["pt-BR"])
                # Se for apenas um pequeno atraso (até 5 min), agendar para o "agora" (daqui a 1s)
                at_ms = now_ms + 1000 
                logger.info(f"Cron: target time {delta_past_ms}ms in past; scheduling +1s instead")
            
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after_run = True
        # Recorrente: mantém-se listado até o utilizador remover ou fim da recorrência
        elif every_seconds:
            schedule = CronSchedule(
                kind="every",
                every_ms=every_seconds * 1000,
                not_before_ms=not_before_ms,
                not_after_ms=not_after_ms,
            )
            delete_after_run = False
        elif cron_expr:
            tz_iana = None
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_user_timezone
                db = SessionLocal()
                try:
                    tz_iana = get_user_timezone(db, self._chat_id, self._phone_for_locale)
                finally:
                    db.close()
            except Exception:
                pass
            schedule = CronSchedule(
                kind="cron",
                expr=cron_expr,
                tz=tz_iana,
                not_before_ms=not_before_ms,
                not_after_ms=not_after_ms,
            )
            delete_after_run = False
        else:
            return "Error: use every_seconds, cron_expr, or target_at_iso/in_seconds"

        # Limites por dia (40 lembretes, 80 total): verificar antes de criar
        at_warning_reminder = False
        if not depends_on_job_id:
            from zapista.cron.service import _compute_next_run
            now_ms = _effective_now_ms()
            next_ms = _compute_next_run(schedule, now_ms)
            if next_ms is not None:
                from datetime import datetime
                from zoneinfo import ZoneInfo
                from backend.database import SessionLocal
                from backend.user_store import get_user_timezone, get_or_create_user
                from backend.limits import check_reminder_limits, LIMIT_REMINDERS_PER_DAY
                from backend.locale import (
                    LIMIT_REMINDERS_PER_DAY_REACHED,
                    LIMIT_TOTAL_PER_DAY_REACHED,
                    LIMIT_WARNING_70,
                )
                tz_iana = "UTC"
                try:
                    db_lim = SessionLocal()
                    try:
                        tz_iana = get_user_timezone(db_lim, self._chat_id) or "UTC"
                        user_lim = get_or_create_user(db_lim, self._chat_id)
                        z = ZoneInfo(tz_iana)
                        target_date = datetime.fromtimestamp(next_ms / 1000.0, tz=z).date()
                        allowed, at_warning_reminder, _, rem_count, _ = check_reminder_limits(
                            self._cron, self._chat_id, target_date, tz_iana,
                            db=db_lim, user_id=user_lim.id,
                        )
                        if not allowed:
                            _lang = self._get_user_lang()
                            if rem_count >= LIMIT_REMINDERS_PER_DAY:
                                return LIMIT_REMINDERS_PER_DAY_REACHED.get(_lang, LIMIT_REMINDERS_PER_DAY_REACHED["pt-BR"])
                            return LIMIT_TOTAL_PER_DAY_REACHED.get(_lang, LIMIT_TOTAL_PER_DAY_REACHED["pt-BR"])
                    finally:
                        db_lim.close()
                except Exception:
                    pass  # em falha (ex.: timezone) deixar criar

        # Verificação de duplicatas com contexto: exact match ou Mimo (últimas 20 msgs)
        dup_result = await self._check_duplicate_with_context(
            message=message,
            schedule=schedule,
        )
        if dup_result:
            return dup_result

        if remind_again_if_unconfirmed_seconds is not None:
            if remind_again_if_unconfirmed_seconds < 900 or remind_again_if_unconfirmed_seconds > 86400:
                return "O adiamento 'lembra de novo se não confirmar' deve estar entre 15 minutos e 24 horas."
        if depends_on_job_id:
            dep = self._cron.get_job(depends_on_job_id.strip().upper()[:16])
            if not dep or getattr(dep.payload, "to", None) != self._chat_id:
                return f"Não encontrei o lembrete \"{depends_on_job_id}\" para encadear. Verifica o id em /lembrete (lista)."
        # has_deadline: apenas para lembretes pontuais (in_seconds); main não remove até confirmar ou 3 lembretes pós-prazo
        use_deadline = has_deadline and in_seconds is not None and in_seconds > 0
        # Lembretes importantes (pontuais): se o user não especificou reenvio, 
        # agendamos 1 follow-up automático em 1h se for importante.
        if is_important and remind_again_if_unconfirmed_seconds is None and delete_after_run:
             remind_again_if_unconfirmed_seconds = 3600 # 1h
             remind_again_max_count = 1
        else:
             remind_again_max_count = 10 # default original para recorrência/deadline se setado

        try:
            job = self._cron.add_job(
                name=message[:30],
                schedule=schedule,
                message=message,
                deliver=True,
                channel=self._channel,
                to=self._chat_id,
                phone_for_locale=getattr(self, "_phone_for_locale", None),
                delete_after_run=delete_after_run and not use_deadline,
                suggested_prefix=suggested_prefix,
                remind_again_if_unconfirmed_seconds=remind_again_if_unconfirmed_seconds,
                remind_again_max_count=remind_again_max_count,
                depends_on_job_id=depends_on_job_id.strip().upper()[:16] if depends_on_job_id else None,
                has_deadline=use_deadline,
                suggested_draft=suggested_draft,
                audio_mode=audio_mode,
                pomodoro_cycle=pomodoro_cycle,
                pomodoro_phase=pomodoro_phase,
                is_important=is_important,
            )
        except ValueError as e:
            if "MAX_REMINDERS_EXCEEDED" in str(e):
                from backend.locale import REMINDER_LIMIT_EXCEEDED
                lang = self._get_user_lang()
                return REMINDER_LIMIT_EXCEEDED.get(lang, REMINDER_LIMIT_EXCEEDED["pt-BR"])
            raise
        if use_deadline and job.schedule.kind == "at" and job.schedule.at_ms:
            at_ms = job.schedule.at_ms + (5 * 60 * 1000)
            self._cron.add_job(
                name=f"{message[:22]} (prazo)",
                schedule=CronSchedule(kind="at", at_ms=at_ms),
                message=message,
                deliver=False,
                channel=self._channel,
                to=self._chat_id,
                phone_for_locale=getattr(self, "_phone_for_locale", None),
                delete_after_run=True,
                payload_kind="deadline_check",
                deadline_check_for_job_id=job.id,
                parent_job_id=job.id,
            )
        # Avisos antes do evento: só quando o tipo de lembrete exige (reunião, voo, consulta...) ou evento muito longo (24h automático)
        pre_reminder_count = 0
        if in_seconds is not None and in_seconds > 0 and use_pre_reminders:
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_default_reminder_lead_seconds, get_extra_reminder_leads_seconds
                from backend.reminder_lead_classifier import AUTO_LEAD_LONG_EVENT_SECONDS
                db = SessionLocal()
                try:
                    if long_event_24h:
                        # Evento muito longo (ex.: > 5 dias): um único aviso 24h antes, sem perguntar ao cliente
                        lead_sec = AUTO_LEAD_LONG_EVENT_SECONDS
                        when_sec = in_seconds - lead_sec
                        if when_sec > 0:
                            at_ms = _effective_now_ms() + when_sec * 1000
                            self._cron.add_job(
                                name=(message[:26] + " (antes)"),
                                schedule=CronSchedule(kind="at", at_ms=at_ms),
                                message=message,
                                deliver=True,
                                channel=self._channel,
                                to=self._chat_id,
                                phone_for_locale=getattr(self, "_phone_for_locale", None),
                                delete_after_run=True,
                                parent_job_id=job.id,
                                audio_mode=audio_mode,
                            )
                            pre_reminder_count = 1
                    else:
                        # Preferências do user (quando tinha onboarding de avisos) ou fallback 24h para novos users
                        default_lead = get_default_reminder_lead_seconds(db, self._chat_id)
                        extra_leads = get_extra_reminder_leads_seconds(db, self._chat_id)
                        if default_lead is None:
                            default_lead = AUTO_LEAD_LONG_EVENT_SECONDS  # 24h para reuniões/compromissos quando user não definiu
                        seen = set()
                        leads = []
                        if default_lead and default_lead not in seen:
                            seen.add(default_lead)
                            leads.append(default_lead)
                        for L in extra_leads:
                            if L and L not in seen:
                                seen.add(L)
                                leads.append(L)
                        leads.sort(reverse=True)
                        for lead_sec in leads[:4]:
                            when_sec = in_seconds - lead_sec
                            if when_sec <= 0:
                                continue
                            at_ms = _effective_now_ms() + when_sec * 1000
                            self._cron.add_job(
                                name=(message[:26] + " (antes)"),
                                schedule=CronSchedule(kind="at", at_ms=at_ms),
                                message=message,
                                deliver=True,
                                channel=self._channel,
                                to=self._chat_id,
                                phone_for_locale=getattr(self, "_phone_for_locale", None),
                                delete_after_run=True,
                                parent_job_id=job.id,
                                audio_mode=audio_mode,
                            )
                            pre_reminder_count += 1
                finally:
                    db.close()
            except Exception:
                pass
        try:
            from datetime import datetime
            from backend.database import SessionLocal
            from backend.reminder_history import add_scheduled
            db = SessionLocal()
            try:
                schedule_at_dt = None
                if job.state.next_run_at_ms:
                    schedule_at_dt = datetime.utcfromtimestamp(job.state.next_run_at_ms / 1000)
                add_scheduled(
                    db,
                    self._chat_id,
                    message,
                    job_id=job.id,
                    schedule_at=schedule_at_dt,
                    channel=self._channel,
                    recipient=self._chat_id,
                )
            finally:
                db.close()
        except Exception:
            pass
        from backend.locale import (
            CRON_REMINDER_SCHEDULED, CRON_PRE_REMINDERS_ADDED, CRON_UNCONFIRMED_RETRY,
            CRON_DEPENDS_ON, CRON_WILL_BE_SENT, CRON_CREATED_BY_CLI,
            CRON_TZ_LABEL_FROM_PHONE, CRON_TZ_LABEL_UTC_FALLBACK, LIMIT_WARNING_70,
        )
        _lang = self._get_user_lang()
        msg = CRON_REMINDER_SCHEDULED.get(_lang, CRON_REMINDER_SCHEDULED["en"]).format(job_id=job.id)
        if pre_reminder_count > 0:
            msg += CRON_PRE_REMINDERS_ADDED.get(_lang, CRON_PRE_REMINDERS_ADDED["en"]).format(count=pre_reminder_count)
        if remind_again_if_unconfirmed_seconds:
            m = remind_again_if_unconfirmed_seconds // 60
            msg += CRON_UNCONFIRMED_RETRY.get(_lang, CRON_UNCONFIRMED_RETRY["en"]).format(minutes=m)
        if depends_on_job_id:
            msg += CRON_DEPENDS_ON.get(_lang, CRON_DEPENDS_ON["en"]).format(job_id=depends_on_job_id)
        if at_warning_reminder:
            msg += "\n\n" + LIMIT_WARNING_70.get(_lang, LIMIT_WARNING_70["pt-BR"])
        # Para lembretes "daqui a X min", mostrar a hora no timezone do usuário (nunca hora do servidor)
        if in_seconds is not None and in_seconds > 0 and job.state.next_run_at_ms:
            at_sec = job.state.next_run_at_ms // 1000
            # Precisão da confirmação:
            # ≤ 5 min → mostrar HH:MM:SS (muito perto, o utilizador quer saber o segundo)
            # > 5 min → arredondar ao minuto mais próximo (HH:MM)
            _show_secs = in_seconds <= 300
            if _show_secs:
                at_sec_display = at_sec
            else:
                at_sec_display = ((at_sec + 30) // 60) * 60
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_user_timezone
                from backend.timezone import format_utc_timestamp_for_user, phone_to_default_timezone
                db = SessionLocal()
                try:
                    tz = get_user_timezone(db, self._chat_id, self._phone_for_locale) or phone_to_default_timezone(self._phone_for_locale or self._chat_id) or "UTC"
                    hora_str = format_utc_timestamp_for_user(at_sec_display, tz, show_seconds=_show_secs)
                    tz_label = CRON_TZ_LABEL_FROM_PHONE.get(_lang, CRON_TZ_LABEL_FROM_PHONE["en"])
                finally:
                    db.close()
            except Exception:
                from backend.timezone import format_utc_timestamp_for_user
                hora_str = format_utc_timestamp_for_user(at_sec, "UTC")
                tz_label = CRON_TZ_LABEL_UTC_FALLBACK.get(_lang, CRON_TZ_LABEL_UTC_FALLBACK["en"])
            msg += CRON_WILL_BE_SENT.get(_lang, CRON_WILL_BE_SENT["en"]).format(time=hora_str, tz=tz_label)
        if self._channel == "cli":
            msg += CRON_CREATED_BY_CLI.get(_lang, CRON_CREATED_BY_CLI["en"])
        return msg

    def _remove_all_jobs(self) -> str:
        """Remove todos os lembretes do utilizador atual. Chamado quando user diz 'delete all', 'remove all', etc."""
        all_jobs = self._cron.list_jobs()
        user_jobs = [
            j for j in all_jobs
            if getattr(j.payload, "to", None) == self._chat_id
        ]
        if not user_jobs:
            _lang = self._get_user_lang()
            from backend.locale import CRON_NO_REMINDERS
            return CRON_NO_REMINDERS.get(_lang, CRON_NO_REMINDERS["en"])
        # Remove cada job e todos os seus sub-jobs (prazos, avisos, etc.)
        # Usa um set para evitar dupla remoção de sub-jobs já eliminados
        removed_ids: set[str] = set()
        count = 0
        for j in user_jobs:
            if j.id not in removed_ids:
                n = self._cron.remove_job_and_deadline_followups(j.id)
                if n > 0:
                    removed_ids.add(j.id)
                    count += 1
        _lang = self._get_user_lang()
        msgs = {
            "pt-PT": f"{count} lembrete(s) removido(s). ✅",
            "pt-BR": f"{count} lembrete(s) removido(s). ✅",
            "es": f"{count} recordatorio(s) eliminado(s). ✅",
            "en": f"{count} reminder(s) removed. ✅",
        }
        return msgs.get(_lang, msgs["en"])

    def _list_jobs(self) -> str:
        """Lista apenas os lembretes do usuário atual (payload.to == chat_id). Isolamento por conversa.
        Nudge proativo, avisos e prazos internos não aparecem — apenas lembretes principais."""
        all_jobs = self._cron.list_jobs()
        jobs = [
            j for j in all_jobs
            if getattr(j.payload, "to", None) == self._chat_id
            and not getattr(j.payload, "is_proactive_nudge", False)
            and not getattr(j.payload, "parent_job_id", None)
            and not getattr(j.payload, "deadline_check_for_job_id", None)
            and not getattr(j.payload, "deadline_main_job_id", None)
        ]
        from backend.locale import CRON_NO_REMINDERS, CRON_REMINDERS_HEADER
        _lang = self._get_user_lang()
        if not jobs:
            return CRON_NO_REMINDERS.get(_lang, CRON_NO_REMINDERS["en"])
        lines = [f"• {j.name} ({j.schedule.kind}) [id: {j.id}]" for j in jobs]
        return CRON_REMINDERS_HEADER.get(_lang, CRON_REMINDERS_HEADER["en"]) + "\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        job_id = sanitize_string(str(job_id), max_len=64)
        if not job_id:
            return "Error: job_id is required for remove"
        # Só permite remover jobs que pertencem a este chat_id (segurança e isolamento)
        from backend.locale import (
            CRON_JOB_NOT_YOURS, CRON_REMOVED, CRON_JOB_NOT_FOUND,
            CRON_JOB_NOT_FOUND_DELIVERED, CRON_JOB_NOT_FOUND_MAYBE_FIRED,
        )
        _lang = self._get_user_lang()
        for j in self._cron.list_jobs():
            if j.id == job_id:
                if getattr(j.payload, "to", None) != self._chat_id:
                    return CRON_JOB_NOT_YOURS.get(_lang, CRON_JOB_NOT_YOURS["en"]).format(job_id=job_id)
                # Remove o job e todos os seus sub-jobs (avisos, prazos, etc)
                removed_count = self._cron.remove_job_and_deadline_followups(job_id)
                if removed_count > 0:
                    return CRON_REMOVED.get(_lang, CRON_REMOVED["en"]).format(job_id=job_id)
                return CRON_JOB_NOT_FOUND.get(_lang, CRON_JOB_NOT_FOUND["en"]).format(job_id=job_id)
        # Lembrete único pode já ter sido executado e removido automaticamente
        try:
            from backend.database import SessionLocal
            from backend.reminder_history import get_reminder_history
            db = SessionLocal()
            try:
                entries = get_reminder_history(db, self._chat_id, kind="delivered", limit=5)
                if entries:
                    last = entries[0]
                    delivered = last.get("delivered_at") or last.get("created_at")
                    if delivered and hasattr(delivered, "strftime"):
                        return CRON_JOB_NOT_FOUND_DELIVERED.get(_lang, CRON_JOB_NOT_FOUND_DELIVERED["en"]).format(
                            job_id=job_id,
                            delivered_at=delivered.strftime("%d/%m/%Y %H:%M"),
                        )
            finally:
                db.close()
        except Exception:
            pass
        return CRON_JOB_NOT_FOUND_MAYBE_FIRED.get(_lang, CRON_JOB_NOT_FOUND_MAYBE_FIRED["en"]).format(job_id=job_id)
