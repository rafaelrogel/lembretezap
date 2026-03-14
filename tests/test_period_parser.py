"""Tests for backend.period_parser: parsing temporal qualifiers in 4 languages."""

from datetime import date

import pytest

from backend.period_parser import parse_period, period_label


# --- Year ---

class TestYear:
    def test_year_pt_para(self):
        assert parse_period("mostre meus lembretes para 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_pt_ano_de(self):
        assert parse_period("ano de 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_pt_em(self):
        assert parse_period("lembretes em 2028") == (date(2028, 1, 1), date(2028, 12, 31))

    def test_year_en_for(self):
        assert parse_period("show my reminders for 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_en_in(self):
        assert parse_period("reminders in 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_en_year(self):
        assert parse_period("year 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_es_para(self):
        assert parse_period("mis recordatorios para 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_es_año(self):
        assert parse_period("año 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_es_del(self):
        assert parse_period("eventos del 2027") == (date(2027, 1, 1), date(2027, 12, 31))

    def test_year_invalid_range(self):
        assert parse_period("para 1899") is None
        assert parse_period("para 2101") is None

    def test_year_para_o_ano(self):
        assert parse_period("para o ano de 2027") == (date(2027, 1, 1), date(2027, 12, 31))


# --- Month ---

class TestMonth:
    def test_month_pt_em(self):
        result = parse_period("em março", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))

    def test_month_pt_para(self):
        result = parse_period("para dezembro", today=date(2026, 3, 10))
        assert result == (date(2026, 12, 1), date(2026, 12, 31))

    def test_month_pt_past_month_uses_next_year(self):
        result = parse_period("em janeiro", today=date(2026, 3, 10))
        assert result == (date(2027, 1, 1), date(2027, 1, 31))

    def test_month_with_year(self):
        result = parse_period("em março de 2028", today=date(2026, 3, 10))
        assert result == (date(2028, 3, 1), date(2028, 3, 31))

    def test_month_en_in(self):
        result = parse_period("in march", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))

    def test_month_en_for(self):
        result = parse_period("for december", today=date(2026, 3, 10))
        assert result == (date(2026, 12, 1), date(2026, 12, 31))

    def test_month_es_en(self):
        result = parse_period("en marzo", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))

    def test_month_es_para(self):
        result = parse_period("para enero", today=date(2026, 3, 10))
        assert result == (date(2027, 1, 1), date(2027, 1, 31))

    def test_february_leap_year(self):
        result = parse_period("em fevereiro", today=date(2028, 1, 1))
        assert result == (date(2028, 2, 1), date(2028, 2, 29))

    def test_february_non_leap_year(self):
        result = parse_period("em fevereiro", today=date(2027, 1, 1))
        assert result == (date(2027, 2, 1), date(2027, 2, 28))


# --- This week ---

class TestThisWeek:
    def test_this_week_pt(self):
        result = parse_period("para esta semana", today=date(2026, 3, 10))  # Tuesday
        assert result == (date(2026, 3, 9), date(2026, 3, 15))

    def test_this_week_en(self):
        result = parse_period("this week", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 9), date(2026, 3, 15))

    def test_this_week_es(self):
        result = parse_period("esta semana", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 9), date(2026, 3, 15))


# --- Next week ---

class TestNextWeek:
    def test_next_week_pt_proxima(self):
        result = parse_period("próxima semana", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 16), date(2026, 3, 22))

    def test_next_week_pt_semana_que_vem(self):
        result = parse_period("semana que vem", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 16), date(2026, 3, 22))

    def test_next_week_en(self):
        result = parse_period("next week", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 16), date(2026, 3, 22))


# --- This month ---

class TestThisMonth:
    def test_this_month_pt(self):
        result = parse_period("este mês", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))

    def test_this_month_en(self):
        result = parse_period("this month", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))

    def test_this_month_es(self):
        result = parse_period("este mes", today=date(2026, 3, 10))
        assert result == (date(2026, 3, 1), date(2026, 3, 31))


# --- Next month ---

class TestNextMonth:
    def test_next_month_pt(self):
        result = parse_period("próximo mês", today=date(2026, 3, 10))
        assert result == (date(2026, 4, 1), date(2026, 4, 30))

    def test_next_month_pt_que_vem(self):
        result = parse_period("mês que vem", today=date(2026, 3, 10))
        assert result == (date(2026, 4, 1), date(2026, 4, 30))

    def test_next_month_en(self):
        result = parse_period("next month", today=date(2026, 3, 10))
        assert result == (date(2026, 4, 1), date(2026, 4, 30))

    def test_next_month_december(self):
        result = parse_period("próximo mês", today=date(2026, 12, 15))
        assert result == (date(2027, 1, 1), date(2027, 1, 31))


# --- Today / Tomorrow ---

class TestTodayTomorrow:
    def test_today_pt(self):
        assert parse_period("para hoje", today=date(2026, 3, 10)) == (date(2026, 3, 10), date(2026, 3, 10))

    def test_today_en(self):
        assert parse_period("for today", today=date(2026, 3, 10)) == (date(2026, 3, 10), date(2026, 3, 10))

    def test_today_es(self):
        assert parse_period("para hoy", today=date(2026, 3, 10)) == (date(2026, 3, 10), date(2026, 3, 10))

    def test_tomorrow_pt(self):
        assert parse_period("para amanhã", today=date(2026, 3, 10)) == (date(2026, 3, 11), date(2026, 3, 11))

    def test_tomorrow_en(self):
        assert parse_period("for tomorrow", today=date(2026, 3, 10)) == (date(2026, 3, 11), date(2026, 3, 11))

    def test_tomorrow_es(self):
        assert parse_period("para mañana", today=date(2026, 3, 10)) == (date(2026, 3, 11), date(2026, 3, 11))


# --- No match ---

class TestNoMatch:
    def test_empty(self):
        assert parse_period("") is None

    def test_unrelated(self):
        assert parse_period("me lembre de beber agua") is None

    def test_just_numbers(self):
        assert parse_period("123") is None


# --- Period label ---

class TestPeriodLabel:
    def test_year_label(self):
        assert period_label(date(2027, 1, 1), date(2027, 12, 31), "pt-BR") == "2027"

    def test_month_label_pt(self):
        assert period_label(date(2027, 3, 1), date(2027, 3, 31), "pt-BR") == "março 2027"

    def test_month_label_en(self):
        assert period_label(date(2027, 3, 1), date(2027, 3, 31), "en") == "March 2027"

    def test_month_label_es(self):
        assert period_label(date(2027, 3, 1), date(2027, 3, 31), "es") == "marzo 2027"

    def test_day_label(self):
        assert period_label(date(2026, 3, 10), date(2026, 3, 10), "pt-BR") == "10/03/2026"

    def test_week_label(self):
        lbl = period_label(date(2026, 3, 9), date(2026, 3, 15), "pt-BR")
        assert "09/03" in lbl and "15/03" in lbl
