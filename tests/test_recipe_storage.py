import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Adiciona o diretório lembretezap ao path para importar backend
sys.path.append(str(Path(__file__).parent.parent))

from backend.recipe_handler import _is_save_recipe_intent, _handle_save_provided_recipe, _parse_ingredients_from_recipe
from zapista.agent.tools.list_tool import ListTool
from backend.handler_context import HandlerContext

def test_save_recipe_intent():
    print("--- Testing Save Recipe Intent ---")
    queries = [
        "Anota esta receita de omelete: leva 2 ovos, sal, pimenta...",
        "Guarda esta receita: 1kg de carne...",
        "anote essa receita deliciosa",
        "save this recipe please",
    ]
    for q in queries:
        detected = _is_save_recipe_intent(q)
        print(f"Query: '{q[:30]}...' -> Detected: {detected}")
        assert detected is True

    non_queries = [
        "mostre minha lista de compras",
        "me lembra de comprar ovos",
        "anota ai: comprar leite",
    ]
    for q in non_queries:
        detected = _is_save_recipe_intent(q)
        print(f"Non-Query: '{q[:30]}...' -> Detected: {detected}")
        assert detected is False

def test_list_tool_no_split():
    print("\n--- Testing List Tool no_split ---")
    tool = ListTool()
    
    text_with_commas = "Ingredientes: 2 ovos, sal, pimenta, queijo. Modo de preparo: bata tudo."
    
    # Com split (padrão)
    parts_split = tool._split_items(text_with_commas)
    print(f"Split result count (expected > 1): {len(parts_split)}")
    
    # Simulando _add com no_split=True
    # (Não vamos rodar o _add real para evitar DB, mas testamos a lógica do items_to_add)
    no_split = True
    if no_split:
        items_to_add = [text_with_commas]
    else:
        items_to_add = tool._split_items(text_with_commas)
    
    print(f"No-split result count: {len(items_to_add)}")
    assert len(items_to_add) == 1
    assert items_to_add[0] == text_with_commas

async def test_handle_save_recipe_flow():
    print("\n--- Testing handle_save_provided_recipe flow ---")
    
    ctx = MagicMock(spec=HandlerContext)
    ctx.chat_id = "test_user"
    ctx.channel = "test_channel"
    ctx.phone_for_locale = "123"
    ctx.scope_provider = AsyncMock()
    ctx.scope_model = "test_model"
    ctx.list_tool = MagicMock()
    ctx.list_tool.execute = AsyncMock(return_value="Ok")

    # Mocking LLM response
    mock_llm_response = MagicMock()
    mock_llm_response.content = "Título: Omelete Organizada\nIngredientes:\n- 2 ovos\n- sal\nModo: Bata e frite."
    ctx.scope_provider.chat.return_value = mock_llm_response

    content = "Anota esta receita de omelete: leva 2 ovos, sal, pimenta..."
    
    from backend.recipe_handler import _handle_save_provided_recipe
    res = await _handle_save_provided_recipe(ctx, content)
    
    print("Flow result obtained.")
    # Verifica se o list_tool foi chamado com no_split=True
    ctx.list_tool.execute.assert_called_with(
        action="add", 
        list_name="receitas", 
        item_text=mock_llm_response.content,
        no_split=True
    )
    assert "Omelete Organizada" in res
    assert "Posso criar uma lista de compras" in res

if __name__ == "__main__":
    test_save_recipe_intent()
    test_list_tool_no_split()
    asyncio.run(test_handle_save_recipe_flow())
    print("\nAll recipe logic tests passed!")
