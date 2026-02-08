"""Cron tool for scheduling reminders and tasks."""

import time
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""
    
    def __init__(self, cron_service: CronService):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
    
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
            "every_seconds = repeat interval (e.g. 86400 = daily, 3600 = every hour); "
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
                    "description": "Repeat every N seconds (e.g. 60 = every minute, 600 = every 10 min)"
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
            return self._add_job(message, every_seconds, in_seconds, cron_expr)
        elif action == "list":
            return self._list_jobs()
        elif action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"
    
    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        in_seconds: int | None,
        cron_expr: str | None,
    ) -> str:
        if not message:
            return "Error: message is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        
        if in_seconds is not None and in_seconds > 0:
            at_ms = int(time.time() * 1000) + in_seconds * 1000
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after_run = True
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
        )
        msg = f"Lembrete agendado (id: {job.id})."
        if self._channel == "cli":
            msg += " (Criado pelo terminal; para receber a notificação no WhatsApp, envie o lembrete pelo próprio WhatsApp.)"
        return msg
    
    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)
    
    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
