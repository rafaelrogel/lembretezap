"""Testes para resolve_response_language (redundância de idioma com base no número)."""

import pytest

from backend.locale import resolve_response_language, phone_to_default_language


def test_resolve_en_but_phone_pt_br_returns_pt_br():
    """DB diz en, número +55 → pt-BR (redundância corrige onboarding mal feito)."""
    assert resolve_response_language("en", "5511999999999@s.whatsapp.net", None) == "pt-BR"


def test_resolve_en_but_phone_351_returns_pt_pt():
    """DB diz en, número +351 → pt-PT."""
    assert resolve_response_language("en", "351912345678@s.whatsapp.net", None) == "pt-PT"


def test_resolve_en_but_phone_34_returns_es():
    """DB diz en, número +34 → es."""
    assert resolve_response_language("en", "34612345678@s.whatsapp.net", None) == "es"


def test_resolve_pt_br_unchanged():
    """DB diz pt-BR → mantém pt-BR."""
    assert resolve_response_language("pt-BR", "5511999999999@s.whatsapp.net", None) == "pt-BR"


def test_resolve_en_phone_44_stays_en():
    """DB diz en, número UK +44 → en (sem conflito)."""
    assert resolve_response_language("en", "447911123456@s.whatsapp.net", None) == "en"


def test_resolve_uses_phone_for_locale_when_provided():
    """phone_for_locale override (ex.: LID com número real)."""
    assert resolve_response_language(
        "en", "xyz@lid", "5511999999999"
    ) == "pt-BR"
