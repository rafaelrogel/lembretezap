import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from backend.handlers import handle_add
from backend.handler_context import HandlerContext

@pytest.mark.asyncio
async def test_repro_add_item_bug_correct():
    """Reproduz o erro onde 'add' é inserido na lista por erro de índice do regex group."""
    
    # Mock do ListTool
    mock_list_tool = MagicMock()
    mock_list_tool.execute = AsyncMock(return_value="Anotado!")
    
    ctx = HandlerContext(
        channel="cli",
        chat_id="user123",
        cron_service=None,
        cron_tool=None,
        list_tool=mock_list_tool,
        phone_for_locale="5511999999999"
    )
    
    # Simula "/add banana"
    # O handler deve extrair "banana" e chamar list_tool.execute(action="add", item_text="banana", ...)
    result = await handle_add(ctx, "/add banana")
    
    # Pega os argumentos da última chamada
    args, kwargs = mock_list_tool.execute.call_args
    print(f"Chamada list_tool.execute com: {kwargs}")
    
    # Se o bug existir, item_text será "add"
    assert kwargs["item_text"] != "add", "ERRO: O handler passou 'add' como item em vez do texto real!"
    assert kwargs["item_text"] == "banana", f"ERRO: Esperava 'banana', veio '{kwargs['item_text']}'"

if __name__ == "__main__":
    asyncio.run(test_repro_add_item_bug_correct())
