"""Testes para o debounce buffer do MessageBus."""
import asyncio
import os
import pytest
from datetime import datetime

from zapista.bus.events import InboundMessage
from zapista.bus.queue import MessageBus


def _make_msg(chat_id: str, content: str, channel: str = "whatsapp") -> InboundMessage:
    return InboundMessage(
        channel=channel,
        sender_id=chat_id,
        chat_id=chat_id,
        content=content,
        timestamp=datetime.now(),
    )


@pytest.fixture(autouse=True)
def patch_buffer_env(monkeypatch):
    """Usa buffer de 0.1s nos testes para não demorar."""
    monkeypatch.setenv("MSG_BUFFER_SECONDS", "0.1")
    monkeypatch.setenv("MSG_BUFFER_MAX", "10")


@pytest.mark.asyncio
async def test_single_message_delivered():
    """Uma mensagem única deve ser entregue após o delay."""
    bus = MessageBus(redis_url=None)
    await bus.publish_inbound(_make_msg("111", "Oi"))
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert msg.content == "Oi"


@pytest.mark.asyncio
async def test_multiple_messages_coalesced():
    """Rajada de mensagens deve ser acumulada em uma única."""
    bus = MessageBus(redis_url=None)
    await bus.publish_inbound(_make_msg("222", "Faz lista de compra"))
    await bus.publish_inbound(_make_msg("222", "Ovo"))
    await bus.publish_inbound(_make_msg("222", "Pão"))
    await bus.publish_inbound(_make_msg("222", "Leite"))

    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert "Faz lista de compra" in msg.content
    assert "Ovo" in msg.content
    assert "Pão" in msg.content
    assert "Leite" in msg.content
    assert msg.metadata.get("_buffer_count") == 4


@pytest.mark.asyncio
async def test_command_passes_immediately():
    """Comandos (/) não entram no buffer — devem chegar imediatamente."""
    bus = MessageBus(redis_url=None)
    await bus.publish_inbound(_make_msg("333", "/feito"))
    # Com buffer de 0.1s, o comando não espera nada
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=0.05)
    assert msg.content == "/feito"


@pytest.mark.asyncio
async def test_different_users_independent():
    """Mensagens de chat_ids diferentes NÃO se misturam."""
    bus = MessageBus(redis_url=None)
    await bus.publish_inbound(_make_msg("AAA", "Msg do usuário A"))
    await bus.publish_inbound(_make_msg("BBB", "Msg do usuário B"))

    msgs = []
    for _ in range(2):
        m = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
        msgs.append(m)

    contents = {m.chat_id: m.content for m in msgs}
    assert contents["AAA"] == "Msg do usuário A"
    assert contents["BBB"] == "Msg do usuário B"


@pytest.mark.asyncio
async def test_buffer_disabled_when_zero(monkeypatch):
    """MSG_BUFFER_SECONDS=0 desativa o buffer — entrega imediata."""
    monkeypatch.setenv("MSG_BUFFER_SECONDS", "0")
    bus = MessageBus(redis_url=None)
    await bus.publish_inbound(_make_msg("444", "mensagem"))
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=0.05)
    assert msg.content == "mensagem"


@pytest.mark.asyncio
async def test_buffer_count_in_metadata():
    """Metadata _buffer_count deve refletir o número de mensagens acumuladas."""
    bus = MessageBus(redis_url=None)
    for text in ["a", "b", "c"]:
        await bus.publish_inbound(_make_msg("555", text))
    msg = await asyncio.wait_for(bus.consume_inbound(), timeout=1.0)
    assert msg.metadata["_buffer_count"] == 3
