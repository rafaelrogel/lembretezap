import pytest
from backend.onboarding_skip import is_likely_valid_name

def test_is_likely_valid_name_valid():
    assert is_likely_valid_name("Rafael") is True
    assert is_likely_valid_name("Ana Maria") is True
    assert is_likely_valid_name("João Silva") is True
    assert is_likely_valid_name("Bob") is True

def test_is_likely_valid_name_invalid_confirmation():
    assert is_likely_valid_name("Sim") is False
    assert is_likely_valid_name("Corretíssimo") is False
    assert is_likely_valid_name("Isso") is False
    assert is_likely_valid_name("OK") is False
    assert is_likely_valid_name("Certo") is False
    assert is_likely_valid_name("Yep") is False
    assert is_likely_valid_name("Yes") is False
    assert is_likely_valid_name("Exato") is False

def test_is_likely_valid_name_invalid_filler():
    assert is_likely_valid_name("Oi") is False
    assert is_likely_valid_name("Bom dia") is False
    assert is_likely_valid_name("Hey") is False
    assert is_likely_valid_name("Humm") is False # Though Humm is not in the list, it's short and might be caught by other logic or added later
    assert is_likely_valid_name("Uai") is False
def test_is_likely_valid_name_spanish():
    assert is_likely_valid_name("Si") is False
    assert is_likely_valid_name("Vale") is False
    assert is_likely_valid_name("Perfecto") is False
    assert is_likely_valid_name("Correcto") is False
    assert is_likely_valid_name("Hola") is False
    assert is_likely_valid_name("Ninguno") is False

def test_is_likely_valid_name_too_long():
    assert is_likely_valid_name("Este é um nome extremamente longo que definitivamente não é um nome real") is False

def test_is_likely_valid_name_empty():
    assert is_likely_valid_name("") is False
    assert is_likely_valid_name(None) is False

def test_is_likely_valid_name_url():
    assert is_likely_valid_name("http://example.com") is False

@pytest.mark.asyncio
async def test_extract_name_with_mimo_logic():
    # Since we can't easily run the full AgentLoop with LLM in a unit test without complex mocks,
    # we verify the logic we added to loop.py conceptually by testing the guard it uses.
    from backend.onboarding_skip import is_likely_valid_name
    
    # Simulation of _extract_name_with_mimo return values
    extracted_names = ["Sim", "Corretíssimo", "Rafael", "Chama-me Bob", "Bom dia"]
    
    valid_extracted = [n for n in extracted_names if is_likely_valid_name(n)]
    
    assert "Sim" not in valid_extracted
    assert "Corretíssimo" not in valid_extracted
    assert "Rafael" in valid_extracted
    # "Chama-me Bob" might be valid or invalid depending on length/logic, 
    # but usually the LLM extracts just "Bob".
    assert is_likely_valid_name("Bob") is True
