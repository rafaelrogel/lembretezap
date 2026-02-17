"""Testes do pré-processamento de texto para TTS (wildcards e horários)."""

import pytest

from zapista.tts.preprocess import (
    normalize_times_for_tts,
    prepare_text_for_tts,
    strip_markdown_for_tts,
)


class TestStripMarkdownForTTS:
    def test_remove_asterisks(self):
        assert strip_markdown_for_tts("*sim*") == "sim"
        assert strip_markdown_for_tts("**negrito**") == "negrito"
        assert strip_markdown_for_tts("Olá *mundo*") == "Olá mundo"

    def test_remove_underscores(self):
        assert strip_markdown_for_tts("_itálico_") == "itálico"
        assert strip_markdown_for_tts("__duplo__") == "duplo"

    def test_empty_unchanged(self):
        assert strip_markdown_for_tts("") == ""
        assert strip_markdown_for_tts("só texto") == "só texto"


class TestNormalizeTimesForTTS:
    def test_h_format_pt(self):
        assert "18 horas" in normalize_times_for_tts("às 18h", "pt-BR")
        assert "18 horas" in normalize_times_for_tts("18h00", "pt-BR")
        assert "18 horas e 30" in normalize_times_for_tts("18h30", "pt-BR")
        assert "9 horas" in normalize_times_for_tts("9h", "pt-PT")

    def test_colon_format_pt(self):
        assert "18 horas" in normalize_times_for_tts("18:00", "pt-BR")
        assert "18 horas e 30" in normalize_times_for_tts("18:30", "pt-BR")
        assert "9 horas e 5" in normalize_times_for_tts("9:05", "pt-BR")

    def test_4digit_pt(self):
        assert "18 horas" in normalize_times_for_tts("Lembrete às 1800", "pt-BR")
        assert "18 horas e 30" in normalize_times_for_tts("1830", "pt-BR")
        assert "9 horas e 30" in normalize_times_for_tts("930", "pt-BR")

    def test_english_hours(self):
        assert "18 hours" in normalize_times_for_tts("18:00", "en")
        assert "18 hours and 30" in normalize_times_for_tts("18h30", "en")

    def test_spanish_y(self):
        assert "18 horas" in normalize_times_for_tts("18:00", "es")
        assert "18 horas y 30" in normalize_times_for_tts("18:30", "es")

    def test_dot_format(self):
        assert "18 horas" in normalize_times_for_tts("18.00", "pt-BR")
        assert "9 horas y 30" in normalize_times_for_tts("9.30", "es")

    def test_dot_h_format(self):
        assert "18 horas" in normalize_times_for_tts("18.00 h", "pt-BR")
        assert "9 hours" in normalize_times_for_tts("9.00h", "en")

    def test_12h_am_pm(self):
        assert "18 horas" in normalize_times_for_tts("6pm", "pt-BR")
        assert "6 hours" in normalize_times_for_tts("6am", "en")
        assert "18 horas e 30" in normalize_times_for_tts("6:30pm", "pt-PT")

    def test_year_not_replaced(self):
        # 2024 = ano, não horário
        assert "2024" in normalize_times_for_tts("em 2024", "pt-BR")
        assert "1999" in normalize_times_for_tts("ano 1999", "pt-BR")

    def test_noon_midnight_words(self):
        assert normalize_times_for_tts("at noon", "en") == "at noon"
        assert normalize_times_for_tts("at midnight", "en") == "at midnight"
        assert "meio-dia" in normalize_times_for_tts("at noon", "pt-BR")
        assert "meia-noite" in normalize_times_for_tts("at midnight", "pt-BR")
        assert "mediodía" in normalize_times_for_tts("at noon", "es")
        assert "medianoche" in normalize_times_for_tts("at midnight", "es")

    def test_24_midnight(self):
        assert "meia-noite" in normalize_times_for_tts("24:00", "pt-BR")
        assert "midnight" in normalize_times_for_tts("24:00", "en")
        assert "medianoche" in normalize_times_for_tts("24:00", "es")

    def test_12_noon(self):
        assert "meio-dia" in normalize_times_for_tts("12:00", "pt-BR")
        assert normalize_times_for_tts("12:00", "en") == "noon"

    def test_dash_format(self):
        assert "18 horas" in normalize_times_for_tts("18-00", "pt-BR")
        assert "9 horas y 30" in normalize_times_for_tts("9-30", "es")

    def test_interval(self):
        assert "18 horas às 19 horas" in normalize_times_for_tts("18h-19h", "pt-BR")
        assert "18 hours to 19 hours" in normalize_times_for_tts("18-19", "en")
        assert "18 horas a 19 horas" in normalize_times_for_tts("18:00-19:00", "es")

    def test_h_min_suffix(self):
        assert "18 horas e 30" in normalize_times_for_tts("18h30m", "pt-BR")
        assert "9 horas y 5" in normalize_times_for_tts("9h05min", "es")

    def test_seconds_ignored(self):
        assert "18 horas" in normalize_times_for_tts("18:00:00", "pt-BR")
        assert "18 horas y 15" in normalize_times_for_tts("18:15:30", "es")

    def test_space_hm(self):
        assert "18 horas" in normalize_times_for_tts("18 00", "pt-BR")
        assert "9 hours and 30" in normalize_times_for_tts("9 30", "en")


class TestPrepareTextForTTS:
    def test_combined(self):
        out = prepare_text_for_tts("*Lembrete* às 18h00", "pt-BR")
        assert "Lembrete" in out and "*" not in out
        assert "18 horas" in out

    def test_empty(self):
        assert prepare_text_for_tts("", "pt-BR") == ""
        assert prepare_text_for_tts("   ", "pt-BR") == "   "
