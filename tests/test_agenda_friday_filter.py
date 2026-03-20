import asyncio
import os
import sys
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, AsyncMock
from zoneinfo import ZoneInfo

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.handler_context import HandlerContext
from backend.views.unificado import handle_eventos_unificado

async def test_agenda_friday_filter():
    print("\n--- Testing 'Next 5 Fridays' Agenda Filter ---")
    
    # Mock CronService with some jobs on different days
    # Friday 20/03 (Today), Friday 27/03, Monday 23/03
    today_dt = datetime(2026, 3, 20, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
    friday_next = today_dt + timedelta(days=7)
    monday = today_dt + timedelta(days=3)

    mock_job1 = MagicMock()
    mock_job1.payload.to = "user123"
    mock_job1.payload.message = "Vitamina (Sexta)"
    mock_job1.state.next_run_at_ms = int(today_dt.timestamp() * 1000)
    mock_job1.payload.parent_job_id = None
    mock_job1.payload.is_proactive_nudge = False

    mock_job2 = MagicMock()
    mock_job2.payload.to = "user123"
    mock_job2.payload.message = "Vitamina (Segunda)"
    mock_job2.state.next_run_at_ms = int(monday.timestamp() * 1000)
    mock_job2.payload.parent_job_id = None
    mock_job2.payload.is_proactive_nudge = False

    mock_job3 = MagicMock()
    mock_job3.payload.to = "user123"
    mock_job3.payload.message = "Vitamina (Proxima Sexta)"
    mock_job3.state.next_run_at_ms = int(friday_next.timestamp() * 1000)
    mock_job3.payload.parent_job_id = None
    mock_job3.payload.is_proactive_nudge = False

    mock_cron_service = MagicMock()
    mock_cron_service.list_jobs.return_value = [mock_job1, mock_job2, mock_job3]

    ctx = HandlerContext(
        channel="cli",
        chat_id="user123",
        cron_service=mock_cron_service,
        cron_tool=None,
        list_tool=None,
        phone_for_locale="5511999999999"
    )

    # Mock DB and clock drift to return 20/03/2026
    # We need to mock get_user_timezone, get_user_language, etc.
    import backend.views.unificado as unificado
    unificado._get_user_tz_and_lang = MagicMock(return_value=(ZoneInfo("UTC"), "pt-BR"))
    
    # Mock clock drift
    import zapista.clock_drift
    zapista.clock_drift.get_effective_time = MagicMock(return_value=today_dt.timestamp())

    # Mock SessionLocal and DB query
    mock_db = MagicMock()
    # Mock events (agenda)
    # Event on Friday 20/03, Saturday 21/03
    mock_ev1 = MagicMock()
    mock_ev1.payload = {"nome": "Evento Sexta"}
    mock_ev1.data_at = today_dt.replace(tzinfo=None)
    mock_ev1.tipo = "evento"
    mock_ev1.deleted = False

    mock_ev2 = MagicMock()
    mock_ev2.payload = {"nome": "Evento Sábado"}
    mock_ev2.data_at = (today_dt + timedelta(days=1)).replace(tzinfo=None)
    mock_ev2.tipo = "evento"
    mock_ev2.deleted = False

    mock_db.query.return_value.filter.return_value.all.return_value = [mock_ev1, mock_ev2]
    
    import backend.database
    backend.database.SessionLocal = MagicMock(return_value=mock_db)

    # Execute request
    content = "me mostre lembretes para as proximas 5 sextas"
    print(f"Request: {content}")
    result = await handle_eventos_unificado(ctx, content)
    
    print("\nResulting View:")
    try:
        print(result)
    except UnicodeEncodeError:
        print(result.encode('ascii', 'replace').decode())
    
    # Verification:
    # 1. Should show "(Sexta)" items
    # 2. Should NOT show "(Segunda)" item
    # 3. Should NOT show "(Sábado)" item
    
    assert "Vitamina (Sexta)" in result
    assert "Vitamina (Proxima Sexta)" in result
    assert "Vitamina (Segunda)" not in result, "Error: Monday reminder shown in Friday filter!"
    assert "Evento Sexta" in result
    assert "Evento Sábado" not in result, "Error: Saturday event shown in Friday filter!"
    
    assert "sextas" in result.lower(), "Header doesn't indicate weekday filter"

    print("\n✅ Verification Successful: Weekday filtering is working perfectly!")

if __name__ == "__main__":
    asyncio.run(test_agenda_friday_filter())
