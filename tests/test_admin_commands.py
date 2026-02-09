"""Testes unitários para God Mode: is_admin, parse_admin_command, handle_admin_command."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_is_admin_empty_env():
    """Sem ADMIN_NUMBERS, ninguém é admin."""
    prev = os.environ.pop("ADMIN_NUMBERS", None)
    try:
        from backend.admin_commands import is_admin
        assert is_admin("351912345678") is False
        assert is_admin("") is False
    finally:
        if prev is not None:
            os.environ["ADMIN_NUMBERS"] = prev


def test_is_admin_with_env():
    """Com ADMIN_NUMBERS definido, apenas esses números são admin."""
    prev = os.environ.get("ADMIN_NUMBERS")
    try:
        os.environ["ADMIN_NUMBERS"] = "351912345678,5511999999999"
        from backend import admin_commands
        # Reload to pick up new env
        from backend.admin_commands import is_admin, _admin_numbers
        admins = _admin_numbers()
        assert "351912345678" in admins
        assert is_admin("351912345678") is True
        assert is_admin("351 912 345 678") is True
        assert is_admin("5511999999999") is True
        assert is_admin("5511999999999@s.whatsapp.net") is True  # sender_id may include @
        assert is_admin("359999999999") is False
    finally:
        if prev is not None:
            os.environ["ADMIN_NUMBERS"] = prev
        else:
            os.environ.pop("ADMIN_NUMBERS", None)


def test_parse_admin_command():
    from backend.admin_commands import parse_admin_command
    assert parse_admin_command("#users") == "users"
    assert parse_admin_command("#USERS") == "users"
    assert parse_admin_command("  #cron  ") == "cron"
    assert parse_admin_command("#server") == "server"
    assert parse_admin_command("#status") == "status"
    assert parse_admin_command("#ai") == "ai"
    assert parse_admin_command("#painpoints") == "painpoints"
    assert parse_admin_command("#system") == "system"
    assert parse_admin_command("#paid") == "paid"
    assert parse_admin_command("#unknown") is None
    assert parse_admin_command("#") is None
    assert parse_admin_command("hello") is None
    assert parse_admin_command("") is None
    assert parse_admin_command("#users extra") is None  # só #cmd sozinho


@pytest.mark.asyncio
async def test_handle_admin_command_status():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#status")
    assert "#status" in out
    assert "God Mode" in out or "status" in out.lower()


@pytest.mark.asyncio
async def test_handle_admin_command_unknown():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#invalid")
    assert "Comando desconhecido" in out or "desconhecido" in out.lower()


@pytest.mark.asyncio
async def test_handle_admin_command_users_mock_db():
    from backend.admin_commands import handle_admin_command
    class FakeSession:
        def query(self, *a):
            q = MagicMock()
            q.count.return_value = 42
            return q
        def close(self):
            pass
    out = await handle_admin_command("#users", db_session_factory=lambda: FakeSession())
    assert "#users" in out
    assert "42" in out


@pytest.mark.asyncio
async def test_handle_admin_command_users_no_db():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#users", db_session_factory=None)
    assert "#users" in out
    assert "não disponível" in out or "DB" in out or "Erro" in out


@pytest.mark.asyncio
async def test_handle_admin_command_cron():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({
            "version": 1,
            "jobs": [
                {"id": "j1", "name": "reminder", "enabled": True, "schedule": {"kind": "at", "atMs": 0}, "payload": {}, "state": {"nextRunAtMs": 1234567890000, "lastRunAtMs": 1234567800000}, "createdAtMs": 0, "updatedAtMs": 0, "deleteAfterRun": False},
            ]
        }, f)
        path = f.name
    try:
        from backend.admin_commands import handle_admin_command
        out = await handle_admin_command("#cron", cron_store_path=Path(path))
        assert "#cron" in out
        assert "1" in out or "job" in out.lower()
    finally:
        os.unlink(path)


@pytest.mark.asyncio
async def test_handle_admin_command_cron_no_file():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#cron", cron_store_path=Path("/nonexistent/jobs.json"))
    assert "#cron" in out
    assert "0" in out or "não encontrado" in out or "não" in out.lower()


@pytest.mark.asyncio
async def test_handle_admin_command_server():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#server")
    assert "#server" in out
    assert "RAM" in out or "Disco" in out or "psutil" in out or "Load" in out


@pytest.mark.asyncio
async def test_handle_admin_command_system():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#system")
    assert "#system" in out


@pytest.mark.asyncio
async def test_handle_admin_command_ai():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#ai")
    assert "#ai" in out


@pytest.mark.asyncio
async def test_handle_admin_command_painpoints():
    from backend.admin_commands import handle_admin_command
    out = await handle_admin_command("#painpoints")
    assert "#painpoints" in out


def test_log_unauthorized_no_raise():
    """log_unauthorized não deve lançar."""
    from backend.admin_commands import log_unauthorized
    log_unauthorized("351912345678", "#users")
