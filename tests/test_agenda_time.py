import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
import asyncio

# Helper for async tests in unittest before 3.8 or to ensure IsolatedAsyncioTestCase works
class TestAgendaTimeLocalization(unittest.IsolatedAsyncioTestCase):

    @patch("backend.views.utils.get_events_in_period")
    @patch("backend.views.utils.get_reminders_in_period")
    @patch("backend.database.SessionLocal")
    @patch("backend.user_store.get_or_create_user")
    @patch("backend.views.unificado.HandlerContext")
    @patch("backend.views.unificado._get_user_tz_and_lang")
    async def test_agenda_time_localization_utc(self, mock_get_tz_lang, mock_ctx, mock_get_user, mock_session, mock_get_reminders, mock_get_events):
        """Verify that an event at 13:43 UTC shows as 13:43 in UTC timezone."""
        from backend.views.unificado import handle_eventos_unificado
        
        # Mock _get_user_tz_and_lang to return (UTC, pt-BR)
        mock_get_tz_lang.return_value = (ZoneInfo("UTC"), "pt-BR")
        
        # Mock user and context
        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_ctx.chat_id = "123456789"
        mock_ctx.phone_for_locale = "123456789"
        
        # Event at 13:43 UTC
        dt_event = datetime(2026, 6, 26, 13, 43, tzinfo=timezone.utc)
        # Note: get_events_in_period returns (date, utc_dt, name, time_str)
        mock_get_events.return_value = [
            (date(2026, 6, 26), dt_event.replace(tzinfo=None), "Consulta médica", "13:43")
        ]
        mock_get_reminders.return_value = []
        
        result = await handle_eventos_unificado(mock_ctx, "meus lembretes para 26/06/2026")
        
        self.assertIn("13:43", result)
        self.assertIn("(UTC)", result)

    @patch("backend.views.utils.get_events_in_period")
    @patch("backend.views.utils.get_reminders_in_period")
    @patch("backend.database.SessionLocal")
    @patch("backend.user_store.get_or_create_user")
    @patch("backend.views.unificado.HandlerContext")
    @patch("backend.views.unificado._get_user_tz_and_lang")
    async def test_agenda_time_localization_europe_lisbon(self, mock_get_tz_lang, mock_ctx, mock_get_user, mock_session, mock_get_reminders, mock_get_events):
        """Verify that an event at 13:43 UTC shows as 14:43 in Europe/Lisbon (WEST)."""
        from backend.views.unificado import handle_eventos_unificado
        
        # Mock _get_user_tz_and_lang to return (Europe/Lisbon, pt-PT)
        tz_lisbon = ZoneInfo("Europe/Lisbon")
        mock_get_tz_lang.return_value = (tz_lisbon, "pt-PT")
        
        # Mock user and context
        mock_user = MagicMock(id=1)
        mock_get_user.return_value = mock_user
        mock_ctx.chat_id = "123456789"
        mock_ctx.phone_for_locale = "123456789"
        
        # Event at 13:43 UTC -> 14:43 in Lisbon (WEST is UTC+1 in June)
        dt_event_utc = datetime(2026, 6, 26, 13, 43, tzinfo=timezone.utc)
        dt_local = dt_event_utc.astimezone(tz_lisbon)
        local_time_str = dt_local.strftime("%H:%M") # Should be 14:43
        
        mock_get_events.return_value = [
            (date(2026, 6, 26), dt_event_utc.replace(tzinfo=None), "Consulta médica", local_time_str)
        ]
        mock_get_reminders.return_value = []
        
        result = await handle_eventos_unificado(mock_ctx, "meus lembretes para 26/06/2026")
        
        self.assertIn(local_time_str, result)
        self.assertIn("(Europe/Lisbon)", result)

    def test_reminder_localized_time(self):
        """Verify get_reminders_in_period returns the correctly localized time string."""
        from backend.views.utils import get_reminders_in_period
        
        mock_ctx = MagicMock()
        mock_job = MagicMock()
        
        # Job at 13:43 UTC (June 26 2026)
        dt_utc = datetime(2026, 6, 26, 13, 43, tzinfo=timezone.utc)
        ts_ms = dt_utc.timestamp() * 1000
        
        mock_job.payload.to = "user123"
        mock_job.payload.message = "Lembrete teste"
        mock_job.state.next_run_at_ms = ts_ms
        # clear other attributes to avoid filtering
        mock_job.payload.parent_job_id = None
        mock_job.payload.is_proactive_nudge = False
        mock_job.payload.deadline_check_for_job_id = None
        mock_job.payload.deadline_main_job_id = None
        
        mock_ctx.chat_id = "user123"
        mock_ctx.cron_service.list_jobs.return_value = [mock_job]
        
        tz_lisbon = ZoneInfo("Europe/Lisbon")
        # Range covering the job
        res = get_reminders_in_period(mock_ctx, tz_lisbon, ts_ms - 1000, ts_ms + 1000)
        
        self.assertEqual(len(res), 1)
        # Verify localized time in the resulting tuple
        dt_result, msg = res[0]
        # In June, Lisbon is UTC+1 (WEST), so 13:43 UTC -> 14:43 LOCAL
        self.assertEqual(dt_result.strftime("%H:%M"), "14:43")

if __name__ == "__main__":
    unittest.main()
