import asyncio
from datetime import datetime, date
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

from backend.handler_context import HandlerContext
from backend.views.unificado import handle_eventos_unificado

async def test_agenda_time():
    print("Testing agenda time display...")
    
    # Mock context
    ctx = MagicMock(spec=HandlerContext)
    ctx.chat_id = "test_user"
    ctx.channel = "whatsapp"
    ctx.phone_for_locale = "351910000000" # Portugal
    ctx.cron_service = MagicMock()
    ctx.cron_tool = None
    ctx.session_manager = MagicMock()
    
    # Mock user timezone to Europe/Lisbon to match the report's successful message
    with patch("backend.user_store.get_user_timezone", return_value="Europe/Lisbon"):
        with patch("backend.user_store.get_user_language", return_value="pt-BR"):
            # Mock effective time to 24/03 21:40 (when user made the request)
            _now_ts = datetime(2026, 3, 24, 21, 40, tzinfo=ZoneInfo("UTC")).timestamp()
            
            with patch("zapista.clock_drift.get_effective_time", return_value=_now_ts):
                # 1. Mock a reminder at 26/03 11:43 UTC
                nr = int(datetime(2026, 3, 26, 11, 43, tzinfo=ZoneInfo("UTC")).timestamp() * 1000)
                job = MagicMock()
                job.payload = MagicMock()
                job.payload.to = "test_user"
                job.payload.message = "Consulta médica"
                job.payload.parent_job_id = None
                job.payload.is_proactive_nudge = False
                job.payload.deadline_check_for_job_id = None
                job.payload.deadline_main_job_id = None
                job.state = MagicMock()
                job.state.next_run_at_ms = nr
                ctx.cron_service.list_jobs.return_value = [job]
                
                # 2. Mock an event at 26/03 13:43 UTC
                from backend.models_db import Event
                ev = MagicMock(spec=Event)
                ev.user_id = 1
                ev.tipo = "evento"
                ev.payload = {"nome": "consulta médica"}
                ev.data_at = datetime(2026, 3, 26, 13, 43) # Naive UTC
                ev.deleted = False
                
                # Mock DB session
                with patch("backend.database.SessionLocal") as mock_session_factory:
                    mock_db = mock_session_factory.return_value
                    mock_user = MagicMock()
                    mock_user.id = 1
                    with patch("backend.user_store.get_or_create_user", return_value=mock_user):
                        # Filter for Event.data_at.between
                        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [ev]
                        
                        # Run the handler
                        result = await handle_eventos_unificado(ctx, "agenda 26/3")
                        
                        print("\nRESULT FOR Europe/Lisbon:")
                        print(result)

    # Mock user timezone to America/Sao_Paulo with 16 min drift
    print("\nTesting with America/Sao_Paulo (drift simulation)...")
    with patch("backend.user_store.get_user_timezone", return_value="America/Sao_Paulo"):
        with patch("backend.user_store.get_user_language", return_value="pt-BR"):
            with patch("zapista.clock_drift.get_effective_time", return_value=_now_ts):
                with patch("backend.database.SessionLocal") as mock_session_factory:
                    mock_db = mock_session_factory.return_value
                    mock_user = MagicMock()
                    mock_user.id = 1
                    with patch("backend.user_store.get_or_create_user", return_value=mock_user):
                        mock_db.query.return_value.filter.return_value.filter.return_value.filter.return_value.filter.return_value.all.return_value = [ev]
                        
                        result = await handle_eventos_unificado(ctx, "agenda 26/3")
                        print("\nRESULT FOR America/Sao_Paulo:")
                        print(result)

if __name__ == "__main__":
    asyncio.run(test_agenda_time())
