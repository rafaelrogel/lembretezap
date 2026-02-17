"""Testes para resolve_response_language: idioma guardado tem sempre prioridade."""

import pytest

from backend.locale import resolve_response_language


def test_stored_language_always_wins():
    """Idioma guardado (DB) nunca é sobrescrito pelo número."""
    assert resolve_response_language("en", "351912345678@s.whatsapp.net", None) == "en"
    assert resolve_response_language("en", "5511999999999@s.whatsapp.net", None) == "en"
    assert resolve_response_language("pt-BR", "351912345678@s.whatsapp.net", None) == "pt-BR"
    assert resolve_response_language("pt-PT", "5511999999999@s.whatsapp.net", None) == "pt-PT"
    assert resolve_response_language("es", "351912345678@s.whatsapp.net", None) == "es"


def test_resolve_pt_br_unchanged():
    """DB diz pt-BR → mantém pt-BR."""
    assert resolve_response_language("pt-BR", "5511999999999@s.whatsapp.net", None) == "pt-BR"


def test_resolve_en_stays_en():
    """DB diz en → mantém en (escolha do user respeitada)."""
    assert resolve_response_language("en", "447911123456@s.whatsapp.net", None) == "en"
    assert resolve_response_language("en", "xyz@lid", "5511999999999") == "en"
