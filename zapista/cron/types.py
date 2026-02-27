"""Cron types."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CronSchedule:
    """Schedule definition for a cron job."""
    kind: Literal["at", "every", "cron"]
    # For "at": timestamp in ms
    at_ms: int | None = None
    # For "every": interval in ms
    every_ms: int | None = None
    # For "cron": cron expression (e.g. "0 9 * * *")
    expr: str | None = None
    # Timezone for cron expressions
    tz: str | None = None
    # Recorrentes: NÃO disparar antes desta data (ms). Ex.: lembretes «a partir de 1º julho»
    not_before_ms: int | None = None
    # Recorrentes: NÃO disparar depois desta data (ms). Ex.: «até fim da semana», simpósio
    not_after_ms: int | None = None


@dataclass
class CronPayload:
    """What to do when the job runs."""
    kind: Literal["system_event", "agent_turn", "deadline_check"] = "agent_turn"
    message: str = ""
    # Deliver response to channel
    deliver: bool = False
    channel: str | None = None  # e.g. "whatsapp"
    to: str | None = None  # e.g. chat_id (pode ser LID)
    phone_for_locale: str | None = None  # número para inferir idioma na entrega quando to é LID
    # "Lembra de novo em X min se não confirmar": segundos até reenviar se não houver reação 👍
    remind_again_if_unconfirmed_seconds: int | None = None
    remind_again_max_count: int = 10  # máx reenvios; 0 = não criar mais follow-ups
    # "Depois de A, lembra B": job_id do lembrete A que deve estar feito antes de B disparar
    depends_on_job_id: str | None = None
    # Para follow-ups (remind_again): job_id do lembrete original (para trigger_dependents)
    parent_job_id: str | None = None
    # Lembrete com prazo: não remover main job ao executar; deadline checker cria 3 lembretes pós-prazo
    has_deadline: bool = False
    # Entregar o lembrete como áudio TTS (PTT) em vez de texto
    audio_mode: bool = False
    # Deadline checker: id do job principal a verificar
    deadline_check_for_job_id: str | None = None
    # Jobs pós-prazo (1,2,3): id do job principal; ao confirmar, remover todos
    deadline_main_job_id: str | None = None
    deadline_post_index: int | None = None  # 1, 2 ou 3
    # Nudge proativo 12h antes (quando user não pediu lembrete): não aparece na lista /lembrete
    is_proactive_nudge: bool = False


@dataclass
class CronJobState:
    """Runtime state of a job."""
    next_run_at_ms: int | None = None
    last_run_at_ms: int | None = None
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
    # Soneca ⏰: quantas vezes o utilizador adiou 5 min (máx 3)
    snooze_count: int = 0


@dataclass
class CronJob:
    """A scheduled job."""
    id: str
    name: str
    enabled: bool = True
    schedule: CronSchedule = field(default_factory=lambda: CronSchedule(kind="every"))
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False


@dataclass
class CronStore:
    """Persistent store for cron jobs."""
    version: int = 1
    jobs: list[CronJob] = field(default_factory=list)
