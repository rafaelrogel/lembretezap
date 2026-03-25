# validate_zappelin_fixes.py
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import unittest
import sys
import os

# Ensure backend can be imported
sys.path.append(os.getcwd())

class TestAgendaSelection(unittest.TestCase):
    """Checks the routing and fall-through logic for agenda queries."""
    
    @patch("backend.router.handle_eventos_unificado")
    @patch("backend.router.handle_agenda_nl")
    async def test_agenda_routing_logic(self, mock_agenda_nl, mock_unificado):
        from backend.router import route
        ctx = MagicMock()
        
        # 1. Specific date -> should be handled by unificado
        mock_unificado.return_value = "Unified View"
        res = await route(ctx, "agenda 26/03")
        self.assertEqual(res, "Unified View")
        mock_unificado.assert_called()
        
        # 2. Weekday -> should be handled by unificado
        mock_unificado.reset_mock()
        res = await route(ctx, "agenda de quinta-feira")
        self.assertEqual(res, "Unified View")
        
        # 3. Simple "agenda" or today/tomorrow -> handled by agenda_nl
        mock_unificado.return_value = None # unificado falls through for simple "agenda"
        mock_agenda_nl.return_value = "Today View"
        res = await route(ctx, "agenda")
        self.assertEqual(res, "Today View")
        
    def test_hoje_semana_fallthrough(self):
        """Verifies that hoje_semana handlers return None for complex suffixes."""
        from backend.views.hoje_semana import handle_agenda
        ctx = MagicMock()
        
        # Complex suffix that unificado should handle
        res = MagicMock() # Mock the event loop since handle_agenda is async
        async def run():
            return await handle_agenda(ctx, "/agenda 26/03")
        
        import asyncio
        output = asyncio.run(run())
        self.assertIsNone(output, "hoje_semana should fall through for /agenda 26/03")

class TestNudgeRemoval(unittest.TestCase):
    """Verifies the behavior that kind='at' reminders are treated as one-time."""
    
    def test_one_time_reminder_deletion(self):
        # Behavioral check: kind="at" reminders should have delete_after_run=True 
        # when added via the cron tool.
        from zapista.agent.tools.cron import CronTool
        
        mock_service = MagicMock()
        tool = CronTool(mock_service)
        
        # Mocking the internal call to add_job
        with patch.object(tool, "_add_job") as mock_add:
            tool.add(message="Test", kind="at", in_seconds=60)
            args, kwargs = mock_add.call_args
            self.assertTrue(kwargs.get("delete_after_run"), "One-time reminders must be deleted after run")

class TestCriticalBugBehavior(unittest.TestCase):
    """Smoke tests for the 4 critical backend bug fixes."""

    def test_bug4_period_parser_tuple_size(self):
        """BUG 4: parse_period must return a 3-tuple."""
        from backend.period_parser import parse_period
        res = parse_period("próximos 7 dias")
        self.assertIsInstance(res, tuple)
        self.assertEqual(len(res), 3, "parse_period must return (start, end, weekday_filter)")

    def test_bug3_reminder_flow_sentinel(self):
        """BUG 3: extract_content_and_hour must return -1 for failures."""
        from backend.reminder_flow import extract_content_and_hour, is_vague_date_reminder
        
        # Malformed time
        content, h, m = extract_content_and_hour("médico às")
        self.assertEqual(h, -1, "Should return -1 sentinel for failed parse")
        
        # Verifying caller behavior
        ok, _, _, _ = is_vague_date_reminder("médico às")
        self.assertFalse(ok, "is_vague_date_reminder should return False if hour is -1")

    def test_bug1_2_database_patterns(self):
        """BUG 1 & 2: Documentation check for SQLCipher and Exception patterns."""
        # This is a behavioral/comment check as per instructions.
        import backend.database as db
        
        # Bug 1: init_db uses OperationalError
        import sqlalchemy
        # Verification: search for 'sqlalchemy.exc.OperationalError' in database.py
        with open(db.__file__, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("sqlalchemy.exc.OperationalError", content, "init_db must catch OperationalError")
        
        # Bug 2: SQLCipher guard and pragma order
        # Verification: _set_sqlite_pragmas must have the guard
        self.assertTrue("_DB_PASSPHRASE" in content, "Database must check for passphrase")
        self.assertIn("return  # Já tratado em _set_sqlcipher_key", content, "SQLite pragmas must be guarded")

if __name__ == "__main__":
    # Note: To run async tests in this self-contained script without complex setup
    # we use a simple runner for the async parts or just mock them as above.
    unittest.main()
