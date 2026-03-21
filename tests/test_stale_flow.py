
import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.handlers.lembrete import handle_recurring_event
from backend.handler_context import HandlerContext
from backend.recurring_event_flow import FLOW_KEY, STAGE_NEED_CONFIRM

@pytest.mark.asyncio
async def test_new_request_clears_stale_flow():
    """Verifica que um pedido de recorrência novo apaga o fluxo anterior pendente."""
    # Mock context and session manager
    mock_session = MagicMock()
    mock_session.metadata = {
        FLOW_KEY: {
            "stage": STAGE_NEED_CONFIRM,
            "event": "pagar contas",
            "cron_expr": "0 9 21 * *",
        }
    }
    
    mock_manager = MagicMock()
    mock_manager.get_or_create.return_value = mock_session
    
    ctx = HandlerContext(
        channel="whatsapp",
        chat_id="123",
        cron_service=None,
        cron_tool=AsyncMock(),
        list_tool=None,
        session_manager=mock_manager,
        phone_for_locale="5511999999999"
    )
    
    # Simula o processamento do handler
    # O handler deve ver que "a cada 2 horas" é um novo pedido (is_scheduled_recurring_event)
    # e deve apagar o FLOW_KEY do metadata.
    
    text = "todo dia 5: tomar vitamina"
    result = await handle_recurring_event(ctx, text)
    
    # Verificamos se session.metadata[FLOW_KEY] agora refere-se ao novo evento
    flow = mock_session.metadata.get(FLOW_KEY)
    assert flow is not None
    assert flow["event"] == "tomar vitamina"
    assert flow["cron_expr"] == "0 9 5 * *"
    assert "pagar contas" not in flow["event"].lower()
    
    assert "Parece que" in result
    assert "todo dia 5" in result

if __name__ == "__main__":
    pytest.main([__file__])
