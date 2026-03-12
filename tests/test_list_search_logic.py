import asyncio
import sys
import os
from pathlib import Path

# Adiciona o diretório lembretezap ao path para importar backend
sys.path.append(str(Path(__file__).parent.parent))

from backend.command_parser import parse
from backend.handlers import handle_add
from backend.handler_context import HandlerContext
from backend.search_handler import _is_search_intent, _parse_items_from_search

def test_command_parser_show_vs_add():
    print("\n--- Testing Command Parser: Show vs Add ---")
    
    # Antigo bug: "mostre lista de filmes de David Lynch" era list_add
    intent = parse("mostre lista de filmes de David Lynch")
    print(f"Intent for 'mostre lista de filmes de David Lynch': {intent}")
    assert intent["type"] == "list_show"
    assert intent["list_name"] == "filme"

    intent = parse("cria lista de filmes do David Lynch")
    print(f"Intent for 'cria lista de filmes do David Lynch': {intent}")
    assert intent["type"] == "list_add" or (intent["type"] == "list_show" and intent["list_name"] == "filme") # Se não tiver item

def test_list_name_extraction():
    print("\n--- Testing List Name Extraction (Articles Filter) ---")
    
    class MockListTool:
        def set_context(self, *args, **kwargs): pass
        async def execute(self, action, list_name, item_text, **kwargs):
            return f"Added to {list_name}: {item_text}"

    ctx = HandlerContext(
        chat_id="123", 
        phone_for_locale="123", 
        channel="test",
        cron_service=None,
        cron_tool=None,
        list_tool=None
    )
    ctx.list_tool = MockListTool()

    # NL: "adiciona os mais famosos dele"
    # normalize_nl_to_command transforma em "/add os mais famosos dele"
    async def run_add_test():
        res = await handle_add(ctx, "/add os mais famosos dele")
        print(f"Result for 'adiciona os mais famosos dele': {res}")
        assert "Added to mercado" in res

        res = await handle_add(ctx, "/add filmes Matrix")
        print(f"Result for 'adiciona filmes Matrix': {res}")
        # "filmes" não é stop word, então deve ser o nome da lista
        assert "Added to filmes" in res or "Added to filme" in res

    asyncio.run(run_add_test())

def test_search_intent_detection():
    print("\n--- Testing Search Intent Detection ---")
    
    queries = [
        "mostre filmes de David Lynch",
        "quais são os livros do Lovecraft",
        "recomende músicas do Queen",
        "filmes com o Brad Pitt",
    ]
    
    for q in queries:
        detected = _is_search_intent(q)
        print(f"Query: '{q}' -> Search Intent: {detected}")
        assert detected is True

    non_queries = [
        "me lembra de comprar pão",
        "anota isso",
        "mostre minha lista de compras",
    ]
    for q in non_queries:
        detected = _is_search_intent(q)
        print(f"Non-Search Query: '{q}' -> Search Intent: {detected}")
        assert detected is False

def test_search_item_parsing():
    print("\n--- Testing Search Item Parsing ---")
    
    perplexity_mock_output = """Aqui estão alguns filmes de David Lynch:
1. Eraserhead (1977)
2. The Elephant Man (1980)
3. **Blue Velvet** (1986)
- Mulholland Drive (2001)
* Inland Empire (2006)
"""
    items = _parse_items_from_search(perplexity_mock_output)
    print(f"Parsed items: {items}")
    assert "Eraserhead (1977)" in items
    assert "The Elephant Man (1980)" in items
    assert "Blue Velvet (1986)" in items
    assert "Mulholland Drive (2001)" in items
    assert "Inland Empire (2006)" in items

if __name__ == "__main__":
    test_command_parser_show_vs_add()
    test_list_name_extraction()
    test_search_intent_detection()
    test_search_item_parsing()
    print("\nAll logic tests passed!")
