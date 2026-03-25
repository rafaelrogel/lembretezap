# tests/test_backend_bugs.py
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest

# Adjust import paths to match your project structure
from backend import (
    database,  # init_db, ENGINE, is_encrypted
    period_parser,
    reminder_flow,
)
from backend.models_db import Base

class TestBug1_PeriodParser_3Tuple:
    """Bug 1: period_parser.py returns 3‑tuple for next N days."""

    def test_next_n_days_returns_3tuple(self):
        text = "próximos 7 dias"
        today = date(2026, 3, 25)

        result = period_parser.parse_period(text, today=today)
        assert result is not None
        assert len(result) == 3
        start, end, weekday_filter = result
        assert start == today
        assert end == today + timedelta(days=7)
        assert weekday_filter is None


class TestBug2_Database_SQLCipherPragmas:
    """Bug 2: SQLCipher + WAL/SYNC pragma ordering in database.py."""

    def test_is_encrypted_logic(self):
        # Check if database indicates it's encrypted when passphrase is set
        from backend import database
        with patch("backend.database._DB_PASSPHRASE", "test_key"), \
             patch("backend.database._is_using_sqlcipher", return_value=True), \
             patch("backend.database._using_sqlcipher", True):
            assert database.is_encrypted() is True

    def test_init_db_logs_schema_errors(self):
        # Make sure migrations don't eat all exceptions
        with patch("backend.database._DB_PASSPHRASE", None), \
             patch("backend.database.ENGINE.connect") as mock_conn_context:
            
            mock_conn = MagicMock()
            mock_conn_context.return_value.__enter__.return_value = mock_conn
            mock_conn.execute.side_effect = Exception("test error")

            with pytest.raises(Exception):  # Should NOT be silently swallowed
                database.init_db()


class TestBug3_ReminderFlow_SilentDefaultTime:
    """Bug 3: reminder_flow.py should not silently default time to 09:00."""

    def test_vague_date_reminder_rejects_malformed_time(self):
        # Case: "médico às" → no valid hour/minute
        text = "médico às"

        # Case A: vague time (date but no hour) — should continue
        is_time, content, date_label = reminder_flow.is_vague_time_reminder(
            "tenho consulta amanhã"
        )
        assert is_time is True

        # Case B: vague date (hour but no date) — should fail when parsing fails
        is_date, content, hour, minute = reminder_flow.is_vague_date_reminder(text)
        assert is_date is False

    def test_extract_content_and_hour_signals_parse_error(self):
        # Directly test the helper
        text = "médico às"  # invalid or incomplete
        content, hour, minute = reminder_flow.extract_content_and_hour(text)

        # NEW: sentinel -1 on parse error
        assert hour == -1
        assert minute == -1
