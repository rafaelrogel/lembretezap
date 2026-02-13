"""Contexto e helpers comuns dos handlers."""

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from zapista.agent.tools.cron import CronTool
    from zapista.agent.tools.list_tool import ListTool
    from zapista.agent.tools.event_tool import EventTool
    from zapista.cron.service import CronService


@dataclass
class HandlerContext:
    """Contexto para handlers: canal, chat, ferramentas (cron, list, event), histórico e Mimo (rever/análises)."""
    channel: str
    chat_id: str
    cron_service: "CronService | None"
    cron_tool: "CronTool | None"
    list_tool: "ListTool | None"
    event_tool: "EventTool | None"
    session_manager: Any = None  # SessionManager: para «rever conversa»
    scope_provider: Any = None  # LLMProvider (Xiaomi Mimo) para rever histórico e perguntas analíticas
    scope_model: str | None = None  # modelo a usar (ex. xiaomi_mimo/mimo-v2-flash)
    main_provider: Any = None  # LLMProvider (DeepSeek) para mensagens empáticas (ex.: atendimento)
    main_model: str | None = None  # modelo principal do agente


def _reply_confirm_prompt(msg: str) -> str:
    """Sufixo padrão para pedir confirmação sem botões."""
    return f"{msg}\n\n1️⃣ Sim  2️⃣ Não"
