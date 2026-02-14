"""Tests for vague reminder message detection."""
from backend.guardrails import is_vague_reminder_message


def test_vague_messages():
    """Mensagens que não descrevem o evento → True."""
    assert is_vague_reminder_message("lembrete amanha 10h") is True
    assert is_vague_reminder_message("lembrete amanhã 10h") is True
    assert is_vague_reminder_message("alerta as 9h") is True
    assert is_vague_reminder_message("lembrete") is True
    assert is_vague_reminder_message("") is True


def test_concrete_messages():
    """Mensagens que descrevem o evento → False."""
    assert is_vague_reminder_message("ir à farmácia amanhã 10h") is False
    assert is_vague_reminder_message("tomar remedio às 8h") is False
    assert is_vague_reminder_message("reunião com João segunda 14h") is False
    assert is_vague_reminder_message("ir ao mercado") is False
