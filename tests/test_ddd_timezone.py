"""Testes para ddd_city_and_tz()."""
import pytest
from backend.timezone import ddd_city_and_tz


@pytest.mark.parametrize("phone, expected_city, expected_iana", [
    # Salvador (DDD 71)
    ("5571919191919", "Salvador", "America/Bahia"),
    ("5571919191919@s.whatsapp.net", "Salvador", "America/Bahia"),
    # São Paulo (DDD 11)
    ("5511999999999", "São Paulo", "America/Sao_Paulo"),
    # Rio de Janeiro (DDD 21)
    ("5521999999999", "Rio de Janeiro", "America/Sao_Paulo"),
    # Manaus (DDD 92)
    ("5592999999999", "Manaus", "America/Manaus"),
    # Fortaleza (DDD 85)
    ("5585999999999", "Fortaleza", "America/Fortaleza"),
    # Recife (DDD 81)
    ("5581999999999", "Recife", "America/Recife"),
    # Brasília (DDD 61)
    ("5561999999999", "Brasília", "America/Sao_Paulo"),
    # Belém (DDD 91)
    ("5591999999999", "Belém", "America/Belem"),
    # Curitiba (DDD 41)
    ("5541999999999", "Curitiba", "America/Sao_Paulo"),
    # Rio Branco/Acre (DDD 68)
    ("5568999999999", "Rio Branco", "America/Rio_Branco"),
    # Porto Velho (DDD 69)
    ("5569999999999", "Porto Velho", "America/Porto_Velho"),
    # Boa Vista (DDD 95)
    ("5595999999999", "Boa Vista", "America/Boa_Vista"),
    # Campo Grande (DDD 67)
    ("5567999999999", "Campo Grande", "America/Campo_Grande"),
])
def test_ddd_city_and_tz_known(phone, expected_city, expected_iana):
    result = ddd_city_and_tz(phone)
    assert result is not None, f"Expected result for phone={phone}, got None"
    city, iana = result
    assert city == expected_city, f"phone={phone}: expected city={expected_city!r}, got {city!r}"
    assert iana == expected_iana, f"phone={phone}: expected iana={expected_iana!r}, got {iana!r}"


@pytest.mark.parametrize("phone", [
    # Portugal
    "351911234567",
    "351911234567@s.whatsapp.net",
    # Argentina
    "5491199999999",
    # DDD inválido (60 não existe)
    "5560999999999",
    # Número muito curto (sem DDD)
    "55",
    "551",
    # Não-numérico limpo
    "abc",
    "",
    None,
    # LID (deve retornar None)
    "123456789@lid",
])
def test_ddd_city_and_tz_returns_none(phone):
    result = ddd_city_and_tz(phone)
    assert result is None, f"Expected None for phone={phone!r}, got {result!r}"
