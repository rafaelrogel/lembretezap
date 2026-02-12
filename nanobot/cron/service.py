"""Cron service for scheduling agent tasks."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

from nanobot.cron.friendly_id import (
    generate_friendly_job_id,
    generate_friendly_job_id_with_prefix,
)
from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule, CronStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """Compute next run time in ms. Respeita not_before_ms para recorrentes (ex.: «a partir de 1º julho»)."""
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None
    
    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        if schedule.not_before_ms and now_ms < schedule.not_before_ms:
            return schedule.not_before_ms  # primeiro disparo na data de início
        return now_ms + schedule.every_ms
    
    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo
            # Só considerar ocorrências >= not_before_ms (evita disparar antes da data de início)
            start_epoch = time.time()
            if schedule.not_before_ms and schedule.not_before_ms > now_ms:
                start_epoch = schedule.not_before_ms / 1000.0
            elif schedule.not_before_ms and schedule.not_before_ms > 0:
                start_epoch = max(time.time(), schedule.not_before_ms / 1000.0)
            # Usar timezone do utilizador para interpretar "0 9 * * *" como 9h no seu fuso (não no do VPS)
            if schedule.tz:
                try:
                    from datetime import datetime
                    tz = ZoneInfo(schedule.tz)
                    start_dt = datetime.fromtimestamp(start_epoch, tz=tz)
                    cron = croniter(schedule.expr, start_dt)
                except Exception:
                    cron = croniter(schedule.expr, start_epoch)
            else:
                cron = croniter(schedule.expr, start_epoch)
            next_time = cron.get_next()
            next_ms = int(next_time * 1000)
            return next_ms if next_ms > now_ms else None
        except Exception:
            return None
    
    return None


class CronService:
    """Service for managing and executing scheduled jobs."""
    
    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None
    ):
        self.store_path = store_path
        self.on_job = on_job  # Callback to execute job, returns response text
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False
    
    def _load_store(self) -> CronStore:
        """Load jobs from disk."""
        if self._store:
            return self._store
        
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text())
                jobs = []
                for j in data.get("jobs", []):
                    jobs.append(CronJob(
                        id=j["id"],
                        name=j["name"],
                        enabled=j.get("enabled", True),
                        schedule=CronSchedule(
                            kind=j["schedule"]["kind"],
                            at_ms=j["schedule"].get("atMs"),
                            every_ms=j["schedule"].get("everyMs"),
                            expr=j["schedule"].get("expr"),
                            tz=j["schedule"].get("tz"),
                            not_before_ms=j["schedule"].get("notBeforeMs"),
                        ),
                        payload=CronPayload(
                            kind=j["payload"].get("kind", "agent_turn"),
                            message=j["payload"].get("message", ""),
                            deliver=j["payload"].get("deliver", False),
                            channel=j["payload"].get("channel"),
                            to=j["payload"].get("to"),
                        ),
                        state=CronJobState(
                            next_run_at_ms=j.get("state", {}).get("nextRunAtMs"),
                            last_run_at_ms=j.get("state", {}).get("lastRunAtMs"),
                            last_status=j.get("state", {}).get("lastStatus"),
                            last_error=j.get("state", {}).get("lastError"),
                        ),
                        created_at_ms=j.get("createdAtMs", 0),
                        updated_at_ms=j.get("updatedAtMs", 0),
                        delete_after_run=j.get("deleteAfterRun", False),
                    ))
                self._store = CronStore(jobs=jobs)
            except Exception as e:
                logger.warning(f"Failed to load cron store: {e}")
                self._store = CronStore()
        else:
            self._store = CronStore()
        
        return self._store
    
    def _save_store(self) -> None:
        """Save jobs to disk."""
        if not self._store:
            return
        
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": self._store.version,
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "enabled": j.enabled,
                    "schedule": {
                        "kind": j.schedule.kind,
                        "atMs": j.schedule.at_ms,
                        "everyMs": j.schedule.every_ms,
                        "expr": j.schedule.expr,
                        "tz": j.schedule.tz,
                        "notBeforeMs": j.schedule.not_before_ms,
                    },
                    "payload": {
                        "kind": j.payload.kind,
                        "message": j.payload.message,
                        "deliver": j.payload.deliver,
                        "channel": j.payload.channel,
                        "to": j.payload.to,
                    },
                    "state": {
                        "nextRunAtMs": j.state.next_run_at_ms,
                        "lastRunAtMs": j.state.last_run_at_ms,
                        "lastStatus": j.state.last_status,
                        "lastError": j.state.last_error,
                    },
                    "createdAtMs": j.created_at_ms,
                    "updatedAtMs": j.updated_at_ms,
                    "deleteAfterRun": j.delete_after_run,
                }
                for j in self._store.jobs
            ]
        }
        
        self.store_path.write_text(json.dumps(data, indent=2))
    
    async def start(self) -> None:
        """Start the cron service."""
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        logger.info(f"Cron service started with {len(self._store.jobs if self._store else [])} jobs")
    
    def stop(self) -> None:
        """Stop the cron service."""
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
    
    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs."""
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)
    
    def _get_next_wake_ms(self) -> int | None:
        """Get the earliest next run time across all jobs."""
        if not self._store:
            return None
        times = [j.state.next_run_at_ms for j in self._store.jobs 
                 if j.enabled and j.state.next_run_at_ms]
        return min(times) if times else None
    
    def _arm_timer(self) -> None:
        """Schedule the next timer tick."""
        if self._timer_task:
            self._timer_task.cancel()
        
        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return
        
        delay_ms = max(0, next_wake - _now_ms())
        delay_s = delay_ms / 1000
        
        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()
        
        self._timer_task = asyncio.create_task(tick())
    
    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        if not self._store:
            return
        
        now = _now_ms()
        due_jobs = [
            j for j in self._store.jobs
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]
        
        for job in due_jobs:
            await self._execute_job(job)
        
        self._save_store()
        self._arm_timer()
    
    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job."""
        start_ms = _now_ms()
        logger.info(f"Cron: executing job '{job.name}' ({job.id})")
        
        try:
            response = None
            if self.on_job:
                response = await self.on_job(job)
            
            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info(f"Cron: job '{job.name}' completed")
            
        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.error(f"Cron: job '{job.name}' failed: {e}")
        
        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()
        
        # Política: eventos únicos (não recorrentes) = remover do cron após entrega bem-sucedida
        # kind="at" = lembrete pontual (uma vez) → remover após executar com sucesso (lista limpa)
        if job.schedule.kind == "at" and job.state.last_status == "ok":
            self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
        elif job.schedule.kind == "at":
            # Falhou: desativar para não repetir indefinidamente; fica no store para debug
            job.enabled = False
            job.state.next_run_at_ms = None
        else:
            # Recorrente: manter listado e agendar próxima execução até o utilizador remover (ou fim da recorrência se implementado)
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
    
    # ========== Public API ==========
    
    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs."""
        store = self._load_store()
        jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))
    
    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
        payload_kind: str = "agent_turn",
        suggested_prefix: str | None = None,
    ) -> CronJob:
        """Add a new job. suggested_prefix: quando dado (ex. pelo MIMO), usa para o ID em vez de derivar da mensagem."""
        logger.debug(
            "Cron add_job: name=%r schedule_kind=%s deliver=%s channel=%s to=%s delete_after_run=%s suggested_prefix=%s",
            name[:50] if name else "",
            getattr(schedule, "kind", "?"),
            deliver,
            channel or "(none)",
            (to[:20] + "...") if to and len(to) > 20 else (to or "(none)"),
            delete_after_run,
            suggested_prefix or "(none)",
        )
        msg_preview = (message or "")[:60] + ("..." if len(message or "") > 60 else "")
        logger.debug("Cron add_job: message_len=%d message_preview=%r", len(message or ""), msg_preview)

        store = self._load_store()

        # Log detalhado para debug (NANOBOT_LOG_LEVEL=DEBUG)
        existing_for_user = [j for j in store.jobs if getattr(j.payload, "to", None) == to]
        logger.debug(
            "Cron add_job: user=%s message=%s schedule_kind=%s every_ms=%s expr=%s at_ms=%s existing_jobs_for_user=%d total_jobs=%d",
            (to or "")[:30],
            (message or "")[:100],
            schedule.kind,
            schedule.every_ms,
            (schedule.expr or "")[:50],
            schedule.at_ms,
            len(existing_for_user),
            len(store.jobs),
        )

        # Verificação de duplicatas: mesmo destinatário + mesma mensagem + mesmo schedule
        msg_norm = (message or "").lower().strip()
        for existing in store.jobs:
            if not existing.enabled:
                continue
            if getattr(existing.payload, "to", None) != to:
                continue
            if (existing.payload.message or "").lower().strip() != msg_norm:
                continue
            if existing.schedule.kind != schedule.kind:
                continue
            if schedule.kind == "every":
                if existing.schedule.every_ms != schedule.every_ms:
                    continue
            elif schedule.kind == "cron":
                if (existing.schedule.expr or "").strip() != (schedule.expr or "").strip():
                    continue
            elif schedule.kind == "at":
                if existing.schedule.at_ms != schedule.at_ms:
                    continue
            else:
                continue
            logger.info(f"Cron: duplicate job detected, returning existing job '{existing.id}'")
            logger.debug("Cron add_job: duplicate returned, total_jobs=%d", len(store.jobs))
            return existing

        now = _now_ms()
        kind = payload_kind if payload_kind in ("agent_turn", "system_event") else "agent_turn"
        existing_ids = [j.id for j in store.jobs]
        if suggested_prefix:
            job_id = generate_friendly_job_id_with_prefix(suggested_prefix, existing_ids)
        else:
            job_id = generate_friendly_job_id(message or name, existing_ids)
        next_run_ms = _compute_next_run(schedule, now)

        logger.debug(
            "Cron add_job: generated job_id=%s next_run_at_ms=%s schedule_at=%s",
            job_id,
            next_run_ms,
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(next_run_ms / 1000)) if next_run_ms else "N/A",
        )

        job = CronJob(
            id=job_id,
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind=kind,
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=CronJobState(next_run_at_ms=next_run_ms),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )

        store.jobs.append(job)
        self._save_store()
        self._arm_timer()

        logger.debug("Cron add_job: job created, total_jobs=%d", len(store.jobs))
        sched_desc = schedule.kind
        if schedule.kind == "at" and schedule.at_ms:
            sched_desc += f" at={time.strftime('%Y-%m-%d %H:%M', time.localtime(schedule.at_ms / 1000))}"
        elif schedule.kind == "every" and schedule.every_ms:
            sched_desc += f" every={schedule.every_ms // 1000}s"
        elif schedule.kind == "cron" and schedule.expr:
            sched_desc += f" expr={schedule.expr!r}"
        logger.info(
            "Cron: added job id=%s name=%r schedule=%s deliver=%s channel=%s to=%s next_run=%s total_jobs=%d",
            job_id,
            name[:40] if name else "",
            sched_desc,
            deliver,
            channel or "—",
            (to[:15] + "...") if to and len(to) > 15 else (to or "—"),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(next_run_ms / 1000)) if next_run_ms else "N/A",
            len(store.jobs),
        )
        if deliver and channel == "cli":
            logger.info("Cron: job will not be delivered to WhatsApp (channel=cli); create reminder from WhatsApp to receive there.")
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before
        
        if removed:
            self._save_store()
            self._arm_timer()
            logger.info(f"Cron: removed job {job_id}")
        
        return removed
    
    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                self._save_store()
                self._arm_timer()
                return job
        return None
    
    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job."""
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if not force and not job.enabled:
                    return False
                await self._execute_job(job)
                self._save_store()
                self._arm_timer()
                return True
        return False
    
    def status(self) -> dict:
        """Get service status."""
        store = self._load_store()
        return {
            "enabled": self._running,
            "jobs": len(store.jobs),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }
