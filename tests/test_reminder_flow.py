"""Tests for reminder flow (vague time/date clarification)."""
from backend.reminder_flow import (
    has_vague_time,
    has_vague_date,
    has_reminder_intent,
    is_vague_time_reminder,
    is_vague_date_reminder,
    parse_time_from_response,
    parse_date_from_response,
    parse_advance_seconds,
    looks_like_advance_preference_yes,
    looks_like_advance_preference_no,
    is_consulta_context,
)


def test_has_vague_time():
    """Tempo vago = data sem hora explícita."""
    assert has_vague_time("tenho de ir ao médico amanhã") is True
    assert has_vague_time("consulta na segunda") is True
    assert has_vague_time("reunião hoje") is True
    assert has_vague_time("ir ao médico amanhã 15h") is False
    assert has_vague_time("reunião às 14h") is False
    assert has_vague_time("ir ao médico") is False


def test_has_reminder_intent():
    """Conteúdo sugere pedido de lembrete."""
    assert has_reminder_intent("tenho de ir ao médico amanhã") is True
    assert has_reminder_intent("consulta amanhã") is True
    assert has_reminder_intent("ir ao dentista segunda") is True
    assert has_reminder_intent("O tempo está bom") is False


def test_is_vague_time_reminder():
    """Detecta evento + tempo vago → iniciar fluxo."""
    ok, content, date = is_vague_time_reminder("tenho de ir ao médico amanhã")
    assert ok is True
    assert "médico" in content or "medico" in content.lower()
    assert date == "amanhã" or date == "amanha"

    ok2, _, _ = is_vague_time_reminder("lembrete amanhã")  # vago (sem conteúdo)
    assert ok2 is False

    ok3, _, _ = is_vague_time_reminder("ir ao médico amanhã 15h")  # tem hora
    assert ok3 is False


def test_parse_time_from_response():
    """Extrai hora da resposta."""
    assert parse_time_from_response("15h") == (15, 0)
    assert parse_time_from_response("15:00") == (15, 0)
    assert parse_time_from_response("14:30") == (14, 30)
    assert parse_time_from_response("10") == (10, 0)
    assert parse_time_from_response("às 9h") == (9, 0)
    assert parse_time_from_response("não sei") is None


def test_parse_advance_seconds():
    """Extrai segundos de antecedência."""
    assert parse_advance_seconds("30 min") == 1800
    assert parse_advance_seconds("1 hora") == 3600
    assert parse_advance_seconds("meia hora") == 1800
    assert parse_advance_seconds("2 horas") == 7200
    assert parse_advance_seconds("nada") is None


def test_looks_like_advance_preference():
    """Preferência de antecedência."""
    assert looks_like_advance_preference_yes("sim, com antecedência") is True
    assert looks_like_advance_preference_yes("30 min antes") is True
    assert looks_like_advance_preference_no("apenas na hora") is True
    assert looks_like_advance_preference_no("só no momento") is True


def test_is_consulta_context():
    """Consulta → mensagem 'A que horas é a sua consulta?'."""
    assert is_consulta_context("ir ao médico") is True
    assert is_consulta_context("consulta com o dentista") is True
    assert is_consulta_context("reunião de trabalho") is False


def test_has_vague_date():
    """Data vaga = hora explícita sem dia."""
    assert has_vague_date("médico às 10h") is True
    assert has_vague_date("consulta às 14:30") is True
    assert has_vague_date("ir ao médico às 10h00") is True
    assert has_vague_date("médico amanhã às 10h") is False  # tem data
    assert has_vague_date("só conversar") is False


def test_is_vague_date_reminder():
    """Detecta evento + hora mas sem data."""
    ok, content, hour, minute = is_vague_date_reminder("médico às 10h00")
    assert ok is True
    assert "médico" in content.lower()
    assert hour == 10
    assert minute == 0

    ok2, _, h2, m2 = is_vague_date_reminder("consulta às 14:30")
    assert ok2 is True
    assert h2 == 14 and m2 == 30


def test_parse_date_from_response():
    """Extrai data da resposta."""
    assert parse_date_from_response("amanhã") == "amanhã" or parse_date_from_response("amanhã") == "amanha"
    assert parse_date_from_response("hoje") == "hoje"
    assert parse_date_from_response("na segunda") == "segunda"
    assert parse_date_from_response("não sei") is None
