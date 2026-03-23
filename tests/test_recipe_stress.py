"""
RECIPE SYSTEM STRESS TESTS
===========================
Tests the full recipe pipeline:
1. Intent detection (_is_recipe_intent, _is_save_recipe_intent)
2. Ingredient parsing (_parse_ingredients_from_recipe)
3. List name derivation (_recipe_query_to_list_name)
4. Command parser integration (RE_RECEITA, category mapping)
5. Confirmation flow (_is_recipe_list_confirm, _is_recipe_list_cancel)
6. Edge cases, i18n, malformed input
7. Concurrent recipe requests
"""

import asyncio
import random
import time
import os
import sys
import re

import pytest

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_rate_limit(monkeypatch):
    import backend.rate_limit
    monkeypatch.setattr(backend.rate_limit, "is_rate_limited", lambda *a, **k: False)
    monkeypatch.setattr(backend.rate_limit, "is_rest_rate_limited", lambda *a, **k: False)


# =============================================================================
# 1. INTENT DETECTION
# =============================================================================

class TestRecipeIntentDetection:
    """Test _is_recipe_intent and _is_save_recipe_intent."""

    def setup_method(self):
        from backend.recipe_handler import _is_recipe_intent, _is_save_recipe_intent
        self.is_recipe = _is_recipe_intent
        self.is_save = _is_save_recipe_intent

    # --- Should detect as recipe intent ---

    @pytest.mark.parametrize("msg", [
        "receita de bolo de chocolate",
        "receita de escondidinho",
        "receita de frango grelhado com legumes",
        "ingredientes para fazer lasanha",
        "ingredientes de bolo de cenoura",
        "ingredientes para churrasco",
        "como fazer risoto de cogumelos",
        "como fazer pão de queijo",
        "lista de ingredientes para mousse de maracujá",
        "faça uma lista de ingredientes para strogonoff",
        "me lembre a receita de brigadeiro",
        "passo a passo para fazer empadão",
        "receita da vovó de pudim",
        "receita para bolo de fubá",
        "ingredientes da feijoada",
    ])
    def test_positive_recipe_intent_pt(self, msg):
        assert self.is_recipe(msg), f"Should detect recipe intent: '{msg}'"

    @pytest.mark.parametrize("msg", [
        "how to make chocolate cake",
        "ingredients for lasagna",
        "recipe for chicken soup",
        "ingredientes para hacer paella",
        "receta de tortilla española",
        "como fazer sushi em casa",
    ])
    def test_positive_recipe_intent_multilang(self, msg):
        assert self.is_recipe(msg), f"Should detect recipe intent: '{msg}'"

    # --- Should NOT detect as recipe intent ---

    @pytest.mark.parametrize("msg", [
        "olá",
        "bom dia",
        "/help",
        "/list mercado add leite",
        "/receita bolo",  # starts with / => excluded
        "boa noite",
        "obrigado",
        "lembrete amanhã 9h",
        "",
        "   ",
        "ok",
        "sim",
        "café",  # too short, no pattern
    ])
    def test_negative_recipe_intent(self, msg):
        assert not self.is_recipe(msg), f"Should NOT detect as recipe: '{msg}'"

    # --- Save recipe intent ---

    @pytest.mark.parametrize("msg", [
        "anote esta receita: 2 ovos, 1 xícara de farinha...",
        "guarda esta receita de bolo de chocolate",
        "salve essa receita que te mandei",
        "save this recipe please",
        "guarda esta receta de paella",
    ])
    def test_positive_save_recipe(self, msg):
        assert self.is_save(msg), f"Should detect save intent: '{msg}'"

    @pytest.mark.parametrize("msg", [
        "receita de bolo",
        "como fazer bolo",
        "olá",
        "/receita salvar",
        "",
        "anote isso",  # too short
    ])
    def test_negative_save_recipe(self, msg):
        assert not self.is_save(msg), f"Should NOT detect save intent: '{msg}'"


# =============================================================================
# 2. INGREDIENT PARSING
# =============================================================================

class TestIngredientParsing:
    """Test _parse_ingredients_from_recipe."""

    def setup_method(self):
        from backend.recipe_handler import _parse_ingredients_from_recipe
        self.parse = _parse_ingredients_from_recipe

    def test_numbered_list(self):
        text = """Ingredientes:
1. 2 xícaras de farinha de trigo
2. 3 ovos
3. 1 xícara de açúcar
4. 1/2 xícara de leite
5. 100g de manteiga

Modo de preparo:
Misture tudo e asse."""
        ingredients = self.parse(text)
        assert len(ingredients) == 5
        assert "2 xícaras de farinha de trigo" in ingredients[0]
        assert "3 ovos" in ingredients[1]

    def test_bullet_list(self):
        text = """Ingredientes:
• 500g de frango
• 1 cebola picada
• 2 dentes de alho
• Sal e pimenta a gosto

Preparo:
Tempere o frango..."""
        ingredients = self.parse(text)
        assert len(ingredients) == 4
        assert "500g de frango" in ingredients[0]

    def test_dash_list(self):
        text = """- 3 tomates maduros
- 1 cebola
- azeite
- sal

Instruções:
Corte tudo."""
        ingredients = self.parse(text)
        assert len(ingredients) == 4

    def test_stops_at_modo_de_preparo(self):
        text = """1. farinha
2. ovos
3. açúcar
Modo de preparo:
4. misture tudo
5. asse por 30min"""
        ingredients = self.parse(text)
        assert len(ingredients) == 3, f"Should stop before 'Modo de preparo', got {len(ingredients)}: {ingredients}"

    def test_stops_at_passos(self):
        text = """1. leite
2. manteiga
Passos:
1. aqueça o leite"""
        ingredients = self.parse(text)
        assert len(ingredients) == 2

    def test_stops_at_instructions(self):
        text = """- flour
- eggs
- sugar
Instructions:
Mix everything together."""
        ingredients = self.parse(text)
        assert len(ingredients) == 3

    def test_empty_input(self):
        assert self.parse("") == []
        assert self.parse(None) == []
        assert self.parse("   ") == []

    def test_no_list_markers(self):
        text = "Bolo de chocolate é muito gostoso. Precisa de farinha."
        ingredients = self.parse(text)
        assert len(ingredients) == 0

    def test_max_30_ingredients(self):
        text = "\n".join(f"{i+1}. ingrediente {i+1}" for i in range(50))
        ingredients = self.parse(text)
        assert len(ingredients) <= 30

    def test_truncates_long_items(self):
        text = f"1. {'x' * 500}"
        ingredients = self.parse(text)
        assert len(ingredients) == 1
        assert len(ingredients[0]) <= 256

    def test_mixed_formats(self):
        text = """Ingredientes:
1. 200g chocolate meio amargo
2. 1 lata de leite condensado
• 1 colher de sopa de manteiga
- 100ml de creme de leite

Modo de preparo:
derreta o chocolate"""
        ingredients = self.parse(text)
        assert len(ingredients) == 4

    def test_asterisk_bullets(self):
        text = """* 2 cups flour
* 3 eggs
* 1 cup sugar"""
        ingredients = self.parse(text)
        assert len(ingredients) == 3

    def test_parentheses_in_items(self):
        text = """1. 2 xícaras de farinha (peneirada)
2. 3 ovos (grandes)
3. 200ml de leite (integral)"""
        ingredients = self.parse(text)
        assert len(ingredients) == 3
        assert "peneirada" in ingredients[0]


# =============================================================================
# 3. LIST NAME DERIVATION
# =============================================================================

class TestListNameDerivation:
    """Test _recipe_query_to_list_name."""

    def setup_method(self):
        from backend.recipe_handler import _recipe_query_to_list_name
        self.derive = _recipe_query_to_list_name

    @pytest.mark.parametrize("query,expected_contains", [
        ("receita de bolo de chocolate", "bolo_de_chocolate"),
        ("receita de escondidinho", "escondidinho"),
        ("ingredientes de lasanha", "lasanha"),
        ("como fazer risoto", "risoto"),
        ("lista de ingredientes para mousse", "mousse"),
    ])
    def test_derives_name_from_query(self, query, expected_contains):
        name = self.derive(query)
        assert name.startswith("compras_"), f"Should start with 'compras_': {name}"
        assert expected_contains in name, f"'{expected_contains}' not in '{name}'"

    def test_empty_fallback(self):
        assert self.derive("") == "compras_receita"
        assert self.derive(None) == "compras_receita"
        assert self.derive("   ") == "compras_receita"

    def test_max_length(self):
        long_query = "receita de " + "a" * 200
        name = self.derive(long_query)
        assert len(name) <= 50  # compras_ (8) + 40 max + some margin

    def test_special_chars_removed(self):
        name = self.derive("receita de bolo @#$ especial!")
        assert "@" not in name
        assert "#" not in name
        assert "$" not in name
        assert "!" not in name

    def test_spaces_become_underscores(self):
        name = self.derive("receita de frango grelhado")
        assert " " not in name
        assert "_" in name


# =============================================================================
# 4. COMMAND PARSER INTEGRATION
# =============================================================================

class TestRecipeCommandParser:
    """Test /receita command and category mapping."""

    def setup_method(self):
        from backend.command_parser import parse, _CATEGORY_TO_LIST
        self.parse = parse
        self.categories = _CATEGORY_TO_LIST

    def test_receita_shortcut(self):
        result = self.parse("/receita bolo de chocolate")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"
        assert "bolo de chocolate" in result["item"]

    def test_receita_category_mapping(self):
        assert self.categories.get("receita") == "receitas"
        assert self.categories.get("receitas") == "receitas"
        assert self.categories.get("recipe") == "receitas"
        assert self.categories.get("recipes") == "receitas"
        assert self.categories.get("receta") == "receitas"
        assert self.categories.get("recetas") == "receitas"

    def test_list_receita_add(self):
        result = self.parse("/list receita add bolo de cenoura")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"

    def test_list_receita_category(self):
        result = self.parse("/list receita brigadeiro")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"
        assert "brigadeiro" in result["item"]

    def test_list_recipe_en(self):
        result = self.parse("/list recipe chocolate cake")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"

    def test_list_receta_es(self):
        result = self.parse("/list receta tortilla española")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"

    def test_nl_add_receita(self):
        result = self.parse("add receita pavê de chocolate")
        assert result is not None
        assert result["type"] == "list_add"
        assert result["list_name"] == "receitas"


# =============================================================================
# 5. CONFIRMATION FLOW
# =============================================================================

class TestRecipeConfirmation:
    """Test confirmation/cancellation for shopping list from recipe."""

    def setup_method(self):
        from backend.confirm_actions import _is_recipe_list_confirm, _is_recipe_list_cancel
        self.is_confirm = _is_recipe_list_confirm
        self.is_cancel = _is_recipe_list_cancel

    @pytest.mark.parametrize("msg", [
        "sim", "s", "yes", "y", "pode", "quero",
        "faz isso", "bora", "claro", "ok", "beleza",
        "pode ser", "vale", "valeu", "do it",
        "quero sim", "pode criar", "cria", "criar",
        "faz a lista", "Sim", "SIM", "OK",
        "Sim!", "sim.", "claro!",
    ])
    def test_confirm_positive(self, msg):
        assert self.is_confirm(msg), f"Should confirm: '{msg}'"

    @pytest.mark.parametrize("msg", [
        "não", "nao", "n", "no", "cancelar", "cancel", "nope",
    ])
    def test_cancel_positive(self, msg):
        assert self.is_cancel(msg), f"Should cancel: '{msg}'"

    @pytest.mark.parametrize("msg", [
        "", "   ", None,
        "receita de bolo",
        "talvez amanhã",
        "a" * 100,
    ])
    def test_confirm_negative(self, msg):
        assert not self.is_confirm(msg or ""), f"Should NOT confirm: '{msg}'"

    def test_cancel_doesnt_match_confirm(self):
        """Confirm and cancel should be mutually exclusive."""
        confirms = ["sim", "yes", "ok", "pode", "quero"]
        cancels = ["não", "nao", "no", "cancelar", "cancel"]
        for c in confirms:
            assert not self.is_cancel(c), f"Cancel shouldn't match confirm: '{c}'"
        for c in cancels:
            assert not self.is_confirm(c), f"Confirm shouldn't match cancel: '{c}'"


# =============================================================================
# 6. EDGE CASES AND MALFORMED INPUT
# =============================================================================

class TestRecipeEdgeCases:
    """Edge cases for the recipe system."""

    def setup_method(self):
        from backend.recipe_handler import (
            _is_recipe_intent, _parse_ingredients_from_recipe,
            _recipe_query_to_list_name,
        )
        self.is_recipe = _is_recipe_intent
        self.parse_ingredients = _parse_ingredients_from_recipe
        self.derive_name = _recipe_query_to_list_name

    def test_recipe_with_unicode_emojis(self):
        assert self.is_recipe("receita de bolo 🎂 de chocolate 🍫")

    def test_recipe_with_accents(self):
        assert self.is_recipe("receita de pão de açúcar com maçã")

    def test_ingredient_with_fractions(self):
        text = """1. ½ xícara de açúcar
2. ¼ colher de sal
3. 1½ litro de água"""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 3

    def test_ingredient_with_measurements(self):
        text = """1. 200g de farinha
2. 100ml de leite
3. 1 colher (sopa) de fermento
4. 250°C no forno"""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) >= 3

    def test_only_preparation_no_ingredients(self):
        text = """Modo de preparo:
1. Misture tudo
2. Asse por 30 minutos"""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 0, f"Should find 0 ingredients, got: {ingredients}"

    def test_recipe_intent_minimum_length(self):
        assert not self.is_recipe("receita")  # too short (< 10)
        assert self.is_recipe("receita de bolo")  # OK

    def test_list_name_with_all_special_chars(self):
        name = self.derive_name("receita de @#$%^&*()")
        assert name.startswith("compras_")
        assert not any(c in name for c in "@#$%^&*()")

    def test_newlines_in_ingredient_list(self):
        text = "1. farinha\n\n\n2. ovos\n\n3. açúcar"
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 3

    def test_mixed_numbered_formats(self):
        text = """1) 2 ovos
2- 1 xícara de leite
3. 200g de farinha"""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 3

    def test_stops_at_directions_en(self):
        text = """1. flour
2. eggs
Directions:
1. Mix flour and eggs."""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 2

    def test_stops_at_como_fazer(self):
        text = """1. frango
2. cebola
Como fazer:
Tempere o frango."""
        ingredients = self.parse_ingredients(text)
        assert len(ingredients) == 2


# =============================================================================
# 7. CONCURRENT RECIPE STRESS TEST
# =============================================================================

@pytest.mark.asyncio
async def test_recipe_concurrent_parsing():
    """Stress test: 200 concurrent recipe intent checks + ingredient parsing."""
    from backend.recipe_handler import (
        _is_recipe_intent, _parse_ingredients_from_recipe,
        _recipe_query_to_list_name,
    )

    recipes = [
        "receita de bolo de chocolate",
        "ingredientes para fazer lasanha",
        "como fazer risoto de cogumelos",
        "receita de frango grelhado",
        "lista de ingredientes para mousse de maracujá",
        "receita da vovó de pudim de leite condensado",
        "how to make sushi at home",
        "ingredientes para hacer paella valenciana",
    ]

    ingredient_texts = [
        "1. farinha\n2. ovos\n3. açúcar\nModo de preparo:\nmisture",
        "• 500g frango\n• 1 cebola\n• sal\nPreparo:\ntempere",
        "- 3 tomates\n- azeite\n- alho\nInstruções:\ncorte",
        "1) 200g chocolate\n2) leite condensado\n3) manteiga\nPassos:\nderreta",
    ]

    results = {"intent_ok": 0, "parse_ok": 0, "name_ok": 0, "errors": []}
    NUM = 200

    async def worker(i):
        try:
            q = random.choice(recipes)
            if not _is_recipe_intent(q):
                results["errors"].append(f"W{i}: intent fail for '{q[:30]}'")
                return
            results["intent_ok"] += 1

            txt = random.choice(ingredient_texts)
            ing = _parse_ingredients_from_recipe(txt)
            if len(ing) < 2:
                results["errors"].append(f"W{i}: parse got {len(ing)} ingredients")
                return
            results["parse_ok"] += 1

            name = _recipe_query_to_list_name(q)
            if not name.startswith("compras_"):
                results["errors"].append(f"W{i}: name='{name}'")
                return
            results["name_ok"] += 1
        except Exception as e:
            results["errors"].append(f"W{i}: {type(e).__name__}: {str(e)[:60]}")

    print(f"\n[RECIPE STRESS] {NUM} concurrent recipe operations...")
    t0 = time.perf_counter()
    await asyncio.gather(*[worker(i) for i in range(NUM)])
    elapsed = time.perf_counter() - t0

    print(f"[RECIPE STRESS] Results: intent={results['intent_ok']} parse={results['parse_ok']} name={results['name_ok']} errors={len(results['errors'])} time={elapsed:.2f}s")
    if results["errors"]:
        for e in results["errors"][:5]:
            print(f"  - {e}")

    assert results["intent_ok"] == NUM, f"Intent failures: {NUM - results['intent_ok']}"
    assert results["parse_ok"] == NUM, f"Parse failures: {NUM - results['parse_ok']}"
    assert results["name_ok"] == NUM, f"Name failures: {NUM - results['name_ok']}"
    assert len(results["errors"]) == 0


# =============================================================================
# 8. ROUTER INTEGRATION (recipe via router path)
# =============================================================================

@pytest.mark.asyncio
async def test_recipe_via_command_parser_stress():
    """Stress: 100 /receita commands through the parser."""
    from backend.command_parser import parse

    recipes_pt = [
        "/receita bolo de chocolate", "/receita escondidinho", "/receita brigadeiro",
        "/receita arroz de pato", "/receita feijoada", "/receita bacalhau à brás",
        "/receita pão de queijo", "/receita coxinha", "/receita empadão",
        "/receita mousse de maracujá",
    ]
    recipes_es = [
        "/list receta tortilla", "/list receta paella", "/list receta gazpacho",
    ]
    recipes_en = [
        "/list recipe chocolate cake", "/list recipe chicken soup",
        "/list recipe banana bread",
    ]
    all_cmds = recipes_pt + recipes_es + recipes_en

    errors = []
    for i in range(100):
        cmd = random.choice(all_cmds)
        result = parse(cmd)
        if result is None:
            errors.append(f"#{i} parse returned None for '{cmd}'")
        elif result.get("type") != "list_add":
            errors.append(f"#{i} type={result.get('type')} for '{cmd}'")
        elif result.get("list_name") != "receitas":
            errors.append(f"#{i} list_name={result.get('list_name')} for '{cmd}'")

    print(f"\n[PARSER STRESS] 100 /receita commands: {100 - len(errors)} OK, {len(errors)} errors")
    if errors:
        for e in errors[:5]:
            print(f"  - {e}")

    assert len(errors) == 0, f"{len(errors)} parser errors"


# =============================================================================
# 9. FULL PIPELINE INTEGRATION (without LLM)
# =============================================================================

@pytest.mark.asyncio
async def test_recipe_full_pipeline_no_llm():
    """
    Test the full recipe pipeline without actual LLM calls:
    1. Intent detection
    2. Ingredient parsing from mock response
    3. List name derivation
    4. Confirmation flow
    """
    from backend.recipe_handler import (
        _is_recipe_intent, _parse_ingredients_from_recipe,
        _recipe_query_to_list_name, _build_recipe_response,
    )
    from backend.confirm_actions import _is_recipe_list_confirm, _is_recipe_list_cancel

    query = "receita de bolo de chocolate"
    assert _is_recipe_intent(query)

    mock_recipe = """Ingredientes:
1. 2 xícaras de farinha de trigo
2. 3 ovos
3. 1 xícara de açúcar
4. 1/2 xícara de leite
5. 100g de manteiga
6. 3 colheres de chocolate em pó

Modo de preparo:
Misture os ingredientes secos. Adicione os ovos e o leite.
Asse a 180°C por 35 minutos."""

    ingredients = _parse_ingredients_from_recipe(mock_recipe)
    assert len(ingredients) == 6, f"Expected 6 ingredients, got {len(ingredients)}: {ingredients}"
    assert "2 xícaras de farinha de trigo" in ingredients[0]
    assert "3 colheres de chocolate em pó" in ingredients[5]

    list_name = _recipe_query_to_list_name(query)
    assert list_name == "compras_bolo_de_chocolate"

    assert _is_recipe_list_confirm("sim")
    assert _is_recipe_list_confirm("quero")
    assert _is_recipe_list_cancel("não")
    assert not _is_recipe_list_confirm("não")
    assert not _is_recipe_list_cancel("sim")

    print("\n[PIPELINE] Full recipe pipeline (no LLM): OK")
    print(f"  Query: {query}")
    print(f"  Ingredients: {len(ingredients)}")
    print(f"  List name: {list_name}")
    print(f"  Confirm/cancel: working")
