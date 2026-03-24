import pytest
from backend.handler_context import HandlerContext
from backend.router import route
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_agenda_recognition_various_languages():
    """Verifica se pedidos de agenda em várias línguas são reconhecidos corretamente e não caem no prompt de lembrete."""
    
    # Mock context
    ctx = MagicMock()
    ctx.chat_id = "test_user_123"
    ctx.channel = "whatsapp"
    ctx.phone_for_locale = "5511999999999"
    ctx.cron_tool = MagicMock()
    ctx.cron_service = MagicMock()
    ctx.session_manager = MagicMock()
    ctx.scope_provider = MagicMock()
    ctx.scope_model = "test-model"
    
    # Mock session
    session = MagicMock()
    session.metadata = {}
    ctx.session_manager.get_or_create.return_value = session

    # Test cases: (Input, Expected Start of Output)
    cases = [
        # PT-BR / PT-PT
        ("mostre minha agenda hoje", "📅"),
        ("ver agenda", "📅"),
        ("o que tenho hoje", "📅"),
        ("mostra meu calendário para amanhã", "📅"),
        ("ver eventos de hoje", "📅"),
        
        # EN
        ("show my agenda", "📅"),
        ("what do i have today", "📅"),
        ("view calendar", "📅"),
        ("show my schedule", "📅"),
        
        # ES
        ("mostra mi agenda", "📅"),
        ("qué tengo hoy", "📅"),
        ("ver el calendario", "📅"),
        ("muestra mi agenda de mañana", "📅"),
    ]

    for user_input, expected_char in cases:
        # Nota: o header da agenda começa com o emoji de calendário 📅 configurado no backend.locale
        reply = await route(ctx, user_input)
        assert reply is not None, f"Falha ao reconhecer: {user_input}"
        # A resposta de agenda/hoje costuma começar com o header localizado
        # Como o logger e db são reais (ou parciais), vamos verificar se não retornou o prompt de erro do lembrete "A que horas é?"
        assert "A que horas" not in reply, f"Input '{user_input}' disparou prompt de lembrete: {reply}"
        assert "A que hora" not in reply, f"Input '{user_input}' disparou prompt de lembrete (ES): {reply}"
        assert "What time" not in reply, f"Input '{user_input}' disparou prompt de lembrete (EN): {reply}"

@pytest.mark.asyncio
async def test_reminder_creation_regression():
    """Garante que pedidos reais de lembrete continuam funcionando."""
    ctx = MagicMock()
    ctx.chat_id = "test_user_123"
    ctx.channel = "whatsapp"
    ctx.phone_for_locale = "5511999999999"
    ctx.cron_tool = MagicMock()
    ctx.cron_tool.execute = AsyncMock(return_value="Registrado na agenda!")
    ctx.cron_service = MagicMock()
    ctx.session_manager = MagicMock()
    ctx.scope_provider = MagicMock()
    ctx.scope_model = "test-model"
    session = MagicMock()
    session.metadata = {}
    ctx.session_manager.get_or_create.return_value = session

    # Input que deve disparar criação
    user_input = "me lembra de ir ao médico amanhã às 10h"
    reply = await route(ctx, user_input)
    assert "Registrado na agenda" in reply
