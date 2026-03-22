"""
Regression tests for reminder hallucination bugs.

Bug 1: Old meeting message in session history causes "beber agua" reminder to be
       described as "reuniao" because the LLM picks up stale context.
       Fix: Prioritize session.metadata[FLOW_KEY]["content"] over LLM extraction.

Bug 2: A new reminder request like "me lembra de comprar presente da mae no sabado"
       was intercepted by handle_pending_confirmation because "sabado" matched the
       time-response pattern. The system then mixed the meeting's 14:00 time with the
       new message subject.
       Fix: _looks_like_new_reminder_request() guard at the top of handle_pending_confirmation.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from zapista.session.manager import Session


# ---------------------------------------------------------------------------
# Bug 1: Old context causes hallucination (metadata priority fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metadata_priority_prevents_hallucination():
    """
    Ensures that when session metadata already has a reminder subject (e.g. "beber agua"),
    that subject is used -- even if the LLM would have hallucinated "reuniao" from old history.
    """
    from backend.handlers.lembrete import handle_pending_confirmation
    from backend.handler_context import HandlerContext
    from backend.reminder_flow import FLOW_KEY

    session_key = "whatsapp:test_user_hallucination"
    session = Session(key=session_key)

    # Stale message from 4 days ago
    old_ts = (datetime.now() - timedelta(days=4)).isoformat()
    session.add_message("user", "lembrete: reuniao Silvia 17h30", timestamp=old_ts)
    session.add_message("assistant", "Lembrete agendado (id: REU01).", timestamp=old_ts)

    # Recent water reminder flow -- assistant just asked "when?"
    session.add_message("user", "lembrete diario: beber 2 litros de agua")
    session.add_message("assistant", "Em que momento quer ser lembrado? Pode ser em 10 min, amanha 8h, todo dia ou a cada 2h.")

    # Metadata correctly stores the subject
    session.metadata[FLOW_KEY] = {
        "stage": "need_when",
        "content": "beber 2 litros de agua",
        "retry_count": 0
    }

    ctx = MagicMock(spec=HandlerContext)
    ctx.channel = "whatsapp"
    ctx.chat_id = "test_user_hallucination"
    ctx.phone_for_locale = None
    ctx.cron_tool = MagicMock()
    ctx.cron_tool.execute = AsyncMock(return_value="Lembrete agendado (id: AG01).")
    ctx.session_manager = MagicMock()
    ctx.session_manager.get_or_create.return_value = session
    ctx.scope_provider = AsyncMock()
    ctx.scope_model = "test-model"

    # Even if LLM hallucinates "reuniao", metadata should win
    mock_res = {
        "cron_expr": "5 17 * * *",
        "message": "reuniao",  # Hallucination!
    }

    with patch("backend.pending_confirmation.try_extract_time_response_cron", new_callable=AsyncMock, return_value=mock_res):
        from backend.handlers.lembrete import handle_pending_confirmation
        print(f"DEBUG Test Setup: session.messages length = {len(session.messages)}")
        result = await handle_pending_confirmation(ctx, "todos os dias as 17h05")
        ctx.cron_tool.execute.assert_called_once()
        _, kwargs = ctx.cron_tool.execute.call_args
        assert kwargs["message"] == "beber 2 litros de agua", (
            f"Expected 'beber 2 litros de agua' but got '{kwargs['message']}' -- "
            "hallucination not prevented!"
        )
        print("[PASS] Bug 1: Metadata priority prevents hallucination")


# ---------------------------------------------------------------------------
# Bug 2: New reminder treated as timing answer (guard fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_reminder_not_treated_as_flow_answer():
    """
    Ensures that a new reminder request like "me lembra de comprar presente da mae no sabado"
    is NOT intercepted by handle_pending_confirmation (even though "sabado" matches the
    time-response pattern).
    """
    from backend.handlers.lembrete import handle_pending_confirmation
    from backend.handler_context import HandlerContext
    from backend.reminder_flow import FLOW_KEY

    session_key = "whatsapp:test_user_new_reminder"
    session = Session(key=session_key)

    # User was being asked about a meeting reminder timing
    session.add_message("user", "reuniao sexta as 14h")
    session.add_message("assistant", "Quando voce quer o lembrete? Pode ser antes ou na hora.")

    ctx = MagicMock(spec=HandlerContext)
    ctx.channel = "whatsapp"
    ctx.chat_id = "test_user_new_reminder"
    ctx.phone_for_locale = None
    ctx.cron_tool = AsyncMock()
    ctx.session_manager = MagicMock()
    ctx.session_manager.get_or_create.return_value = session
    ctx.scope_provider = AsyncMock()
    ctx.scope_model = "test-model"

    # This should NOT be treated as an answer -- it's a brand new reminder request
    result = await handle_pending_confirmation(ctx, "me lembra de comprar presente da mae no sabado")

    assert result is None, (
        f"Expected None (pass-through to next handler) but got '{result}' -- "
        "new reminder was incorrectly intercepted by pending confirmation flow!"
    )
    ctx.cron_tool.execute.assert_not_called()
    print("[PASS] Bug 2: New reminder request correctly bypasses pending confirmation flow")


if __name__ == "__main__":
    asyncio.run(test_metadata_priority_prevents_hallucination())
    asyncio.run(test_new_reminder_not_treated_as_flow_answer())
