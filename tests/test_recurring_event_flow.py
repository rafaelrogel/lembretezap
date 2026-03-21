"""Tests for recurring event flow."""
from backend.recurring_event_flow import (
    is_scheduled_recurring_event,
    parse_recurring_schedule,
    format_schedule_for_display,
    parse_end_date_response,
    looks_like_confirm_yes,
    looks_like_confirm_no,
)


def test_is_scheduled_recurring_event():
    """Detecta eventos recorrentes típicos."""
    assert is_scheduled_recurring_event("academia segunda 19h") is True
    assert is_scheduled_recurring_event("aulas de inglês terça 10h") is True
    assert is_scheduled_recurring_event("artes marciais quarta 18h") is True
    assert is_scheduled_recurring_event("curso de piano segunda e quarta 14h") is True
    assert is_scheduled_recurring_event("ir ao mercado") is False


def test_parse_recurring_schedule():
    """Extrai evento + cron de mensagens."""
    r = parse_recurring_schedule("academia segunda 19h")
    assert r is not None
    event, cron, hour, minute = r
    assert "academia" in event.lower()
    assert "0 19 * * 1" == cron
    assert hour == 19

    r2 = parse_recurring_schedule("aulas terça e quinta 10h")
    assert r2 is not None
    _, cron2, h2, _ = r2
    assert h2 == 10
    # Pode ser um dia (4) ou vários (2,4) conforme regex
    assert "0 10" in cron2

    r3 = parse_recurring_schedule("treino segunda a sexta 7h")
    assert r3 is not None
    _, cron3, _, _ = r3
    assert "1-5" in cron3


def test_format_schedule_for_display():
    """Formata cron para exibição."""
    assert "segunda às 19h" in format_schedule_for_display("0 19 * * 1")
    assert "segunda a sexta" in format_schedule_for_display("0 8 * * 1-5")
    assert "segunda" in format_schedule_for_display("0 19 * * 1,3") and "quarta" in format_schedule_for_display("0 19 * * 1,3")
    
    # Monthly
    assert "todo dia 21 às 9h" == format_schedule_for_display("0 9 21 * *")
    assert "every day 21 at 9h" == format_schedule_for_display("0 9 21 * *", lang="en")
    assert "todos los días 21 a las 9h" == format_schedule_for_display("0 9 21 * *", lang="es")
    
    # Languages
    assert "monday at 8h" == format_schedule_for_display("0 8 * * 1", lang="en")
    assert "lunes a las 8h" == format_schedule_for_display("0 8 * * 1", lang="es")
    assert "monday to friday at 8h" == format_schedule_for_display("0 8 * * 1-5", lang="en")


def test_parse_end_date_response():
    """Interpreta resposta sobre até quando."""
    assert parse_end_date_response("indefinido") == "indefinido"
    assert parse_end_date_response("para sempre") == "indefinido"
    assert parse_end_date_response("fim da semana") == "fim_semana"
    assert parse_end_date_response("fim do mês") == "fim_mes"
    assert parse_end_date_response("fim do ano") == "fim_ano"
    assert parse_end_date_response("não sei") is None  # ambíguo, não é indefinido
    
    # Specific years
    assert parse_end_date_response("até o fim de 2028") == "year:2028"
    assert parse_end_date_response("until end of 2030") == "year:2030"
    assert parse_end_date_response("fin de 2027") == "year:2027"
    
    # Specific dates
    assert parse_end_date_response("até 31/12/2026") == "date:2026-12-31"
    assert parse_end_date_response("until 10/10") is not None # should parse as some date


def test_looks_like_confirm():
    """Confirmação sim/não."""
    assert looks_like_confirm_yes("sim") is True
    assert looks_like_confirm_yes("quero") is True
    assert looks_like_confirm_no("não") is True
    assert looks_like_confirm_no("cancelar") is True
