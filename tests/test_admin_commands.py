"""Testes unitários para God Mode: senha, ativação por chat, parse_admin_command, handle_admin_command."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_god_mode_password_empty():
    """Sem GOD_MODE_PASSWORD, senha nunca confere."""
    prev = os.environ.pop("GOD_MODE_PASSWORD", None)
    try:
        from backend.admin_commands import is_god_mode_password, get_god_mode_password
        assert get_god_mode_password() == ""
        assert is_god_mode_password("qualquer") is False
    finally:
        if prev is not None:
            os.environ["GOD_MODE_PASSWORD"] = prev


def test_god_mode_password_match():
    """Com GOD_MODE_PASSWORD definido, só essa senha confere."""
    prev = os.environ.get("GOD_MODE_PASSWORD")
    try:
        os.environ["GOD_MODE_PASSWORD"] = "minhasenha123"
        from backend import admin_commands
        from backend.admin_commands import is_god_mode_password, get_god_mode_password
        assert get_god_mode_password() == "minhasenha123"
        assert is_god_mode_password("minhasenha123") is True
        assert is_god_mode_password("  minhasenha123  ") is True
        assert is_god_mode_password("errada") is False
        assert is_god_mode_password("") is False
    finally:
        if prev is not None:
            os.environ["GOD_MODE_PASSWORD"] = prev
        else:
            os.environ.pop("GOD_MODE_PASSWORD", None)


def test_god_mode_activate_and_check():
    """Activate god-mode para um chat_id; is_god_mode_activated retorna True."""
    from backend.admin_commands import activate_god_mode, is_god_mode_activated
    activate_god_mode("5511999999999@s.whatsapp.net")
    assert is_god_mode_activated("5511999999999@s.whatsapp.net") is True
    assert is_god_mode_activated("outro_chat") is False


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
