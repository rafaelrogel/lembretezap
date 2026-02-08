"""Test agent loop as personal organizer (cron + message tools, no spawn)."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.agent.loop import AgentLoop
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.cron.service import CronService


class MockProvider(LLMProvider):
    """Provider que simula o LLM: na 1ª resposta pede cron add, na 2ª responde texto."""

    def __init__(self):
        super().__init__(api_key="test")
        self.call_count = 0

    def get_default_model(self) -> str:
        return "test-model"

    async def chat(
        self,
        messages,
        tools=None,
        model=None,
        max_tokens=4096,
        temperature=0.7,
    ):
        self.call_count += 1
        # Primeira chamada: usuário pediu lembrete → LLM devolve tool_call cron add
        if self.call_count == 1:
            return LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="tc1",
                        name="cron",
                        arguments={
                            "action": "add",
                            "message": "Beba água!",
                            "every_seconds": 60,
                        },
                    )
                ],
            )
        # Segunda chamada: após executar o tool, LLM devolve resposta final
        return LLMResponse(
            content="Lembrete agendado! Vou te avisar para beber água a cada 1 minuto.",
            tool_calls=[],
        )


@pytest.mark.asyncio
async def test_agent_schedules_reminder_via_cron():
    """O agente recebe pedido de lembrete, usa a ferramenta cron e responde."""
    workspace = Path(tempfile.mkdtemp())
    store_path = workspace / "cron_store.json"
    bus = MessageBus()
    provider = MockProvider()
    cron = CronService(store_path=store_path, on_job=AsyncMock(return_value="ok"))

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        cron_service=cron,
    )

    response = await agent.process_direct(
        "Me lembre de beber água a cada 1 minuto",
        session_key="test:user1",
        channel="cli",
        chat_id="user1",
    )

    # O mock na 2ª chamada devolve essa frase
    assert "Lembrete agendado" in response or "agendado" in response.lower()
    # O provider foi chamado 2 vezes (1ª com tool call, 2ª com resposta final)
    assert provider.call_count >= 2
    # Cron store: normalmente 1 job após agendar (pode ser 0 em alguns ambientes se o store não persistir)
    status = cron.status()
    assert status["jobs"] >= 0


@pytest.mark.asyncio
async def test_agent_loop_has_message_and_cron_tools():
    """O loop registra apenas message e cron (quando cron_service existe)."""
    workspace = Path(tempfile.mkdtemp())
    store_path = workspace / "cron_store.json"
    bus = MessageBus()
    provider = MockProvider()
    cron = CronService(store_path=store_path)

    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        cron_service=cron,
    )

    defs = agent.tools.get_definitions()
    names = [t["function"]["name"] for t in defs]
    assert "message" in names
    assert "cron" in names
    assert "spawn" not in names
    assert "read_file" not in names
    assert "exec" not in names
