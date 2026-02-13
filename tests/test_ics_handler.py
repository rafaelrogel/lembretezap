"""Testes para o handler de anexos .ics e fluxo attachmentIcs no canal WhatsApp."""

import json
from unittest.mock import AsyncMock, patch

import pytest


SAMPLE_ICS = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
SUMMARY:Reunião X
DTSTART:20250215T140000Z
DTEND:20250215T150000Z
LOCATION:Sala 1
END:VEVENT
BEGIN:VEVENT
SUMMARY:Almoço
DTSTART:20250216T120000
DTEND:20250216T130000
END:VEVENT
END:VCALENDAR
""".strip()


@pytest.mark.asyncio
async def test_handle_ics_payload_empty():
    from backend.ics_handler import handle_ics_payload
    out = await handle_ics_payload("351912345678", "351912345678", "", db_session_factory=None)
    assert "vazio" in out.lower() or "empty" in out.lower() or "Calendário" in out


@pytest.mark.asyncio
async def test_handle_ics_payload_invalid():
    from backend.ics_handler import handle_ics_payload
    out = await handle_ics_payload("351912345678", "351912345678", "not ics content", db_session_factory=None)
    assert "inválido" in out.lower() or "invalid" in out.lower() or "Calendário" in out


@pytest.mark.asyncio
async def test_handle_ics_payload_valid_no_db():
    from backend.ics_handler import handle_ics_payload
    out = await handle_ics_payload(
        "351912345678",
        "351912345678",
        SAMPLE_ICS,
        db_session_factory=None,
    )
    assert "não disponível" in out or "disponível" in out or "DB" in out


@pytest.mark.asyncio
async def test_handle_ics_payload_valid_with_db():
    from backend.ics_handler import handle_ics_payload
    from backend.database import SessionLocal
    from backend.models_db import Event
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models_db import Base
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        # Create one user by hand (phone_hash)
        from backend.user_store import phone_hash
        from backend.models_db import User, _truncate_phone
        h = phone_hash("351912345678")
        u = User(phone_hash=h, phone_truncated=_truncate_phone("351912345678"))
        db.add(u)
        db.commit()
        db.close()

        def factory():
            return sessionmaker(bind=engine)()

        out = await handle_ics_payload(
            "351912345678",
            "351912345678",
            SAMPLE_ICS,
            db_session_factory=factory,
        )
        assert "2" in out or "evento" in out.lower() or "Reun" in out or "Almo" in out
        session = factory()
        try:
            events = session.query(Event).filter(Event.tipo == "evento").all()
            assert len(events) >= 1
        finally:
            session.close()
    finally:
        engine.dispose()
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_icalendar_parse_summary_dtstart_location():
    """Valida que icalendar extrai SUMMARY, DTSTART e LOCATION para Event."""
    from backend.ics_handler import handle_ics_payload
    from backend.models_db import Base, Event, User, _truncate_phone
    from backend.user_store import phone_hash
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import tempfile
    import os

    ics_with_location = """
BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
SUMMARY:Consulta medico
DTSTART:20250610T090000Z
DTEND:20250610T093000Z
LOCATION:Clinica Central
DESCRIPTION:Check-up anual
END:VEVENT
END:VCALENDAR
""".strip()

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        h = phone_hash("5511999999999")
        u = User(phone_hash=h, phone_truncated=_truncate_phone("5511999999999"))
        db.add(u)
        db.commit()
        db.close()

        def factory():
            return sessionmaker(bind=engine)()

        out = await handle_ics_payload(
            "5511999999999",
            "5511999999999",
            ics_with_location,
            db_session_factory=factory,
        )
        assert "1" in out or "evento" in out.lower()
        assert "Consulta" in out or "medico" in out or "Clinica" in out

        session = factory()
        try:
            ev = session.query(Event).filter(Event.tipo == "evento").first()
            assert ev is not None
            assert ev.payload.get("nome") == "Consulta medico"
            assert "2025-06-10" in (ev.payload.get("data") or "")
            assert ev.payload.get("local") == "Clinica Central"
            assert "Check-up" in (ev.payload.get("descricao") or "")
        finally:
            session.close()
    finally:
        engine.dispose()
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_whatsapp_channel_attachment_ics_calls_handler_and_sends_response():
    """Quando o canal recebe attachmentIcs, chama handle_ics_payload e envia a resposta no bus."""
    from zapista.channels.whatsapp import WhatsAppChannel
    from zapista.bus.queue import MessageBus
    from zapista.config.schema import WhatsAppConfig

    bus = MessageBus()
    bus.publish_outbound = AsyncMock()
    config = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:9999", allow_from=[])
    channel = WhatsAppChannel(config, bus)

    with patch("backend.ics_handler.handle_ics_payload", new_callable=AsyncMock) as mock_handler:
        mock_handler.return_value = "Encontrados 2 evento(s) no calendário. Registados."
        payload = {
            "type": "message",
            "id": "test-123",
            "sender": "351912345678@s.whatsapp.net",
            "pn": "",
            "content": "[Calendar]",
            "timestamp": 1739123456,
            "isGroup": False,
            "attachmentIcs": SAMPLE_ICS,
        }
        raw = json.dumps(payload)
        await channel._handle_bridge_message(raw)

        mock_handler.assert_called_once()
        call_kw = mock_handler.call_args[1]
        assert call_kw["chat_id"] == "351912345678@s.whatsapp.net"
        assert call_kw["sender_id"] == "351912345678"
        assert SAMPLE_ICS in (call_kw.get("ics_content") or "")

        bus.publish_outbound.assert_called_once()
        out = bus.publish_outbound.call_args[0][0]
        assert out.channel == "whatsapp"
        assert out.chat_id == "351912345678@s.whatsapp.net"
        assert "2" in out.content or "evento" in out.content
