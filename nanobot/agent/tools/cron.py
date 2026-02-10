"""Cron tool for scheduling reminders and tasks."""

import time
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule
from nanobot.cron.friendly_id import get_prefix_from_list
from backend.sanitize import sanitize_string, validate_cron_expr, MAX_MESSAGE_LEN

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(
        self,
        cron_service: CronService,
        scope_provider: "LLMProvider | None" = None,
        scope_model: str = "",
    ):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._scope_provider = scope_provider
        self._scope_model = (scope_model or "").strip()
    
    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id
    
    @property
    def name(self) -> str:
        return "cron"
    
    @property
    def description(self) -> str:
        return (
            "Schedule one-time or recurring reminders. Actions: add, list, remove. "
            "For add: in_seconds = one-time (e.g. 120 = in 2 min); "
            "every_seconds = repeat interval (min 1800 = 30 min, e.g. 3600 = every hour, 86400 = daily); "
            "cron_expr = fixed times (e.g. '0 9 * * *' = daily at 9h, '0 10 * * 1' = every Monday at 10h)."
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
                    "description": "Reminder message (required for add)"
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Repeat every N seconds (minimum 1800 = 30 min, e.g. 3600 = hourly)"
                },
                "in_seconds": {
                    "type": "integer",
                    "description": "One-time reminder in N seconds (e.g. 120 = in 2 minutes)"
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression for fixed times (e.g. '0 9 * * *' = daily at 9h)"
                },
                "job_id": {
                    "type": "string",
                    "description": "Job ID (for remove)"
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
        cron_expr: str | None = None,
        job_id: str | None = None,
        **kwargs: Any
    ) -> str:
        if action == "add":
            from backend.guardrails import is_absurd_request
            absurd = is_absurd_request(message)
            if absurd:
                return absurd
            prefix = get_prefix_from_list(message or "")
            if prefix is None and self._scope_provider and self._scope_model:
                prefix = await self._ask_mimo_abbreviation(message or "")
            return self._add_job(message, every_seconds, in_seconds, cron_expr, suggested_prefix=prefix)
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
                "Reply with ONLY 2 or 3 uppercase letters to use as a short ID (e.g. AL for lunch, PIX for payment). "
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

    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        in_seconds: int | None,
        cron_expr: str | None,
        suggested_prefix: str | None = None,
    ) -> str:
        message = sanitize_string(message or "", MAX_MESSAGE_LEN)
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        if cron_expr and not validate_cron_expr(cron_expr):
            return "Error: expressão cron inválida (use 5 campos: min hora dia mês dia-semana)"
        if in_seconds is not None and (in_seconds < 0 or in_seconds > 86400 * 365):
            return "Error: in_seconds deve estar entre 0 e 1 ano"
        if every_seconds is not None and (every_seconds < 1800 or every_seconds > 86400 * 30):
            return "O intervalo mínimo para lembretes recorrentes é 30 minutos. Ex.: «a cada 30 minutos» ou «a cada 1 hora»."

        # Pontual (não recorrente): após a entrega o job é removido do cron (esquecido pelo sistema); pode existir histórico noutra camada
        if in_seconds is not None and in_seconds > 0:
            at_ms = int(time.time() * 1000) + in_seconds * 1000
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after_run = True
        # Recorrente: mantém-se listado até o utilizador remover ou fim da recorrência
        elif every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
            delete_after_run = False
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
            delete_after_run = False
        else:
            return "Error: use every_seconds (repeat), in_seconds (once), or cron_expr"
        
        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after_run,
            suggested_prefix=suggested_prefix,
        )
        # Avisos antes do evento (preferências do onboarding): 1 default + até 3 extras
        pre_reminder_count = 0
        if in_seconds is not None and in_seconds > 0:
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_default_reminder_lead_seconds, get_extra_reminder_leads_seconds
                db = SessionLocal()
                try:
                    default_lead = get_default_reminder_lead_seconds(db, self._chat_id)
                    extra_leads = get_extra_reminder_leads_seconds(db, self._chat_id)
                    seen = set()
                    leads = []
                    if default_lead and default_lead not in seen:
                        seen.add(default_lead)
                        leads.append(default_lead)
                    for L in extra_leads:
                        if L and L not in seen:
                            seen.add(L)
                            leads.append(L)
                    leads.sort(reverse=True)  # maior antecedência primeiro
                    for lead_sec in leads[:4]:  # max 4 (1 default + 3 extras)
                        when_sec = in_seconds - lead_sec
                        if when_sec <= 0:
                            continue
                        at_ms = int(time.time() * 1000) + when_sec * 1000
                        self._cron.add_job(
                            name=(message[:26] + " (antes)"),
                            schedule=CronSchedule(kind="at", at_ms=at_ms),
                            message=message,
                            deliver=True,
                            channel=self._channel,
                            to=self._chat_id,
                            delete_after_run=True,
                        )
                        pre_reminder_count += 1
                finally:
                    db.close()
            except Exception:
                pass
        try:
            from backend.database import SessionLocal
            from backend.reminder_history import add_scheduled
            db = SessionLocal()
            try:
                add_scheduled(db, self._chat_id, message)
            finally:
                db.close()
        except Exception:
            pass
        msg = f"Lembrete agendado (id: {job.id})."
        if pre_reminder_count > 0:
            msg += f" + {pre_reminder_count} aviso(s) antes do evento (conforme as tuas preferências)."
        # Para lembretes "daqui a X min", mostrar a hora no timezone do utilizador
        if in_seconds is not None and in_seconds > 0 and job.state.next_run_at_ms:
            at_sec = job.state.next_run_at_ms // 1000
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_user_timezone
                from backend.timezone import format_utc_timestamp_for_user
                db = SessionLocal()
                try:
                    tz = get_user_timezone(db, self._chat_id)
                    hora_str = format_utc_timestamp_for_user(at_sec, tz)
                finally:
                    db.close()
            except Exception:
                from datetime import datetime
                hora_str = datetime.fromtimestamp(at_sec).strftime("%H:%M")
            msg += f" Será enviado às {hora_str} (no teu fuso). Mantém o ZapAssist ligado para receberes a notificação."
        if self._channel == "cli":
            msg += " (Criado pelo terminal; para receber no WhatsApp, envia o lembrete pelo próprio WhatsApp.)"
        return msg
    
    def _list_jobs(self) -> str:
        """Lista apenas os lembretes do utilizador atual (payload.to == chat_id). Isolamento por conversa."""
        all_jobs = self._cron.list_jobs()
        jobs = [j for j in all_jobs if getattr(j.payload, "to", None) == self._chat_id]
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
        return f"Job {job_id} não encontrado."
