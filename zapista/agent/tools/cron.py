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
    
    def set_context(self, channel: str, chat_id: str, phone_for_locale: str | None = None) -> None:
        """Set the current session context for delivery. phone_for_locale: número para inferir idioma na entrega (quando chat_id é LID)."""
        self._channel = channel
        self._chat_id = chat_id
        self._phone_for_locale = phone_for_locale

    def set_allow_relaxed_interval(self, allow: bool) -> None:
        """Para este turno: cliente insistiu, permitir intervalo até 30 min."""
        self._allow_relaxed_interval = allow

    def _get_allow_relaxed(self, explicit: bool | None = None) -> bool:
        return explicit if explicit is not None else getattr(self, "_allow_relaxed_interval", False)

    def _get_user_lang(self) -> str:
        """Idioma do utilizador para mensagens (pt-PT, pt-BR, es, en). Usa preferência guardada; senão infere pelo número."""
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
            "message = WHAT to remind (e.g. 'ir à farmácia', 'tomar remédio') — required. Never 'lembrete' or 'alerta'. "
            "If user says 'lembrete amanhã 10h' without event, ask 'De que é o lembrete?' first. "
            "For add: CRITICAL: DO NOT CALCULATE TIME. Parsing is done by the system. "
            "ALWAYS pass the exact time text from the user in 'time_input' (e.g. 'daqui a 5 min', 'amanhã 9h'). "
            "IGNORE 'in_seconds' and 'target_at_iso' unless explicitly constructing a machine-generated timestamp. "
            "System will interpret 'time_input' in the User's Timezone. "
            "every_seconds = repeat; cron_expr = fixed times (interpreted in user timezone when stored). "
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
                    "enum": ["add", "list", "remove"],
                    "description": "Action: add, list, or remove"
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
        **kwargs: Any
    ) -> str:
        logger.info(f"CronTool.execute inputs: action={action}, msg={message}, time_input={time_input}, target={target_at_iso}, in_seconds={in_seconds}, every={every_seconds}, cron={cron_expr}, chat_id={self._chat_id}, channel={self._channel}")

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
                        tz_iana = get_user_timezone(db, self._chat_id) or phone_to_default_timezone(self._chat_id) or "UTC"
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
                    f"Utilizador quer criar lembrete: «{message[:200]}»\n"
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
    ) -> str:
        message = sanitize_string(message or "", MAX_MESSAGE_LEN)
        if not message:
            return "Error: message is required for add"
        # Mensagem vaga (ex.: "lembrete amanhã 10h" sem dizer o quê) → pedir clarificação
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
                        tz_name = get_user_timezone(db, self._chat_id) or phone_to_default_timezone(self._chat_id) or "UTC"
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
                    in_seconds = max(1, (at_ms - now_ms) // 1000)
                except Exception as e:
                    logger.error(f"Failed to parse target_at_iso '{target_at_iso}': {e}")
                    return f"Error parsing time: {target_at_iso}. Use format YYYY-MM-DD HH:MM:SS"
            else:
                now_ms = _effective_now_ms()
                at_ms = now_ms + in_seconds * 1000

            if at_ms <= _effective_now_ms():
                # Relógio ou skew: evitar job no passado (nunca dispararia)
                now_ms = _effective_now_ms()
                at_ms = now_ms + 60 * 1000
                logger.warning("Cron: target time in past; scheduling in 1 min instead")
            
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
                    tz_iana = get_user_timezone(db, self._chat_id)
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
            if remind_again_if_unconfirmed_seconds < 60 or remind_again_if_unconfirmed_seconds > 3600:
                return "O adiamento 'lembra de novo se não confirmar' deve estar entre 1 e 60 minutos."
        if depends_on_job_id:
            dep = self._cron.get_job(depends_on_job_id.strip().upper()[:16])
            if not dep or getattr(dep.payload, "to", None) != self._chat_id:
                return f"Não encontrei o lembrete \"{depends_on_job_id}\" para encadear. Verifica o id em /lembrete (lista)."
        # has_deadline: apenas para lembretes pontuais (in_seconds); main não remove até confirmar ou 3 lembretes pós-prazo
        use_deadline = has_deadline and in_seconds is not None and in_seconds > 0
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
                depends_on_job_id=depends_on_job_id.strip().upper()[:16] if depends_on_job_id else None,
                has_deadline=use_deadline,
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
        msg = f"Lembrete agendado (id: {job.id})."
        if pre_reminder_count > 0:
            msg += f" + {pre_reminder_count} aviso(s) antes do evento (conforme as tuas preferências)."
        if remind_again_if_unconfirmed_seconds:
            m = remind_again_if_unconfirmed_seconds // 60
            msg += f" Se não confirmares com 👍, relembro em {m} min."
        if depends_on_job_id:
            msg += f" Dispara depois de marcar \"{depends_on_job_id}\" como feito."
        if at_warning_reminder:
            from backend.locale import LIMIT_WARNING_70
            _lang = self._get_user_lang()
            msg += "\n\n" + LIMIT_WARNING_70.get(_lang, LIMIT_WARNING_70["pt-BR"])
        # Para lembretes "daqui a X min", mostrar a hora no timezone do utilizador (nunca hora do servidor)
        if in_seconds is not None and in_seconds > 0 and job.state.next_run_at_ms:
            at_sec = job.state.next_run_at_ms // 1000
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_user_timezone
                from backend.timezone import format_utc_timestamp_for_user, phone_to_default_timezone
                db = SessionLocal()
                try:
                    tz = get_user_timezone(db, self._chat_id) or phone_to_default_timezone(self._chat_id) or "UTC"
                    hora_str = format_utc_timestamp_for_user(at_sec, tz)
                    tz_label = "no teu fuso"
                finally:
                    db.close()
            except Exception:
                # Nunca usar datetime.fromtimestamp(at_sec) sem tz: seria hora local do servidor (ex. 14:56 em vez de 21:45)
                from backend.timezone import format_utc_timestamp_for_user
                hora_str = format_utc_timestamp_for_user(at_sec, "UTC")
                tz_label = "UTC (configura /tz para ver no teu fuso)"
            msg += f" Será enviado às {hora_str} ({tz_label}). Mantém o Zapista ligado para receberes a notificação. Se não receberes à hora indicada, verifica em /definições o horário silencioso."
        if self._channel == "cli":
            msg += " (Criado pelo terminal; para receber no WhatsApp, envia o lembrete pelo próprio WhatsApp.)"
        return msg
    
    def _list_jobs(self) -> str:
        """Lista apenas os lembretes do utilizador atual (payload.to == chat_id). Isolamento por conversa.
        Nudge proativo (is_proactive_nudge) não aparece — é surpresa 12h antes."""
        all_jobs = self._cron.list_jobs()
        jobs = [
            j for j in all_jobs
            if getattr(j.payload, "to", None) == self._chat_id
            and not getattr(j.payload, "is_proactive_nudge", False)
        ]
        if not jobs:
            return "Nenhum lembrete agendado."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Lembretes agendados:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        job_id = sanitize_string(str(job_id), max_len=64)
        if not job_id:
            return "Error: job_id is required for remove"
        # Só permite remover jobs que pertencem a este chat_id (segurança e isolamento)
        for j in self._cron.list_jobs():
            if j.id == job_id:
                if getattr(j.payload, "to", None) != self._chat_id:
                    return f"Job {job_id} não te pertence."
                if self._cron.remove_job(job_id):
                    return f"Removido: {job_id}"
                return f"Job {job_id} não encontrado."
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
                        return (
                            f"Job {job_id} não está na lista (lembretes únicos são removidos após disparar). "
                            f"O último lembrete entregue foi em {delivered.strftime('%d/%m/%Y %H:%M')}. "
                            "Use 'rever lembretes' para ver o histórico completo."
                        )
            finally:
                db.close()
        except Exception:
            pass
        return f"Job {job_id} não encontrado. Se era um lembrete único, pode já ter sido executado. Use 'rever lembretes' para ver o histórico."
