import pytest
from dataclasses import dataclass
from backend.sensitive_data_filter import (
    check_credentials_regex,
    check_sensitive_data,
    get_refusal_message,
    SensitiveDataResult,
    is_safe_intent_reminder
)

# Mock provider for LLM tests
@dataclass
class LLMResponse:
    content: str

class MockLLMProvider:
    def __init__(self, response_json: str):
        self.response_json = response_json
        self.last_prompt = ""

    async def chat(self, messages, tools=None, model=None, max_tokens=200, temperature=0, **kwargs):
        self.last_prompt = messages[0]["content"]
        return LLMResponse(content=self.response_json)

def test_credentials_regex_blocked():
    # Card number
    assert check_credentials_regex("Minha conta é 4111 1111 1111 1111").blocked is True # Valid Luhn (fake but follows pattern)
    # API Key Explicit
    assert check_credentials_regex("Use a chave sk-abc12345678901234567890").blocked is True
    assert check_credentials_regex("Bearer abc123def456").blocked is True
    # API Key Assignment
    assert check_credentials_regex("api_key=123456789").blocked is True
    assert check_credentials_regex("token: mySecretTokenValue").blocked is True
    # Password Assignment
    assert check_credentials_regex("senha: 123456").blocked is True
    assert check_credentials_regex("my password is 'secret'").blocked is True
    assert check_credentials_regex("contraseña: gato123").blocked is True
    # PIN
    assert check_credentials_regex("o meu pin é 4321").blocked is True
    assert check_credentials_regex("access code: 9988").blocked is True
    # PEM
    assert check_credentials_regex("-----BEGIN RSA PRIVATE KEY-----").blocked is True

def test_credentials_regex_allowed():
    assert check_credentials_regex("lembrar de comprar pão").blocked is False
    # Concepts only (no assignment separators like : or =)
    assert check_credentials_regex("lembre-me de trocar a senha do gmail").blocked is False
    assert check_credentials_regex("mudar o token da vpn").blocked is False
    assert check_credentials_regex("o PIN do cartão deve ser trocado").blocked is False

def test_safe_intent_heuristics():
    # PT
    assert is_safe_intent_reminder("Lembre-me de trocar a senha do GMAIL") is True
    assert is_safe_intent_reminder("mudar o código do portão") is True
    assert is_safe_intent_reminder("cancelar a minha chave API") is True
    # EN
    assert is_safe_intent_reminder("Remind me to rotate my API key") is True
    assert is_safe_intent_reminder("reset the login password") is True
    # ES
    assert is_safe_intent_reminder("Recuérdame cambiar la contraseña del correo") is True
    
    # Must NOT be safe if value is present (even if it matches safe verb)
    # Note: Regex for assignment will trigger first anyway, but test it here
    assert is_safe_intent_reminder("Mudar senha para 123456") is False # contains "senha para" (not exactly assignment in our regex yet, but the logic should catch it if we improve)
    # Wait, "senha para 123456" matches password_is or password_assignment? No.
    # But if we say "senha: 123456", it should be handled by regex before intent check.

def test_edge_cases():
    # Poetic usage (might be blocked by regex if it looks like assignment)
    # "senha do meu coração é amor" -> matches password_is pattern ("senha ... é ...")
    assert check_credentials_regex("a senha do meu coração é amor").blocked is True 
    # This is expected behavior for precision: we prefer blocking "senha é X" even if X is poetic.
    
    # Mentioning ONLY the keyword
    assert check_credentials_regex("Esqueci a minha senha").blocked is False
    assert check_credentials_regex("Onde fica o token?").blocked is False

@pytest.mark.asyncio
async def test_sensitive_data_full_flow():
    # Safe intent should pass at Stage 1 (intent heuristics)
    res = await check_sensitive_data("Lembre-me de trocar a senha do gmail")
    assert res.blocked is False
    assert res.stage == "intent"

    # Explicit secret should block at Stage 1 (regex high confidence)
    res = await check_sensitive_data("A chave é sk-12345678901234567890")
    assert res.blocked is True
    assert res.stage == "regex"

@pytest.mark.asyncio
async def test_sensitive_data_llm_integration():
    # Political (Stage 2)
    mock = MockLLMProvider('{"blocked": true, "reason": "political", "category": "political", "language": "pt-br"}')
    res = await check_sensitive_data("Eu voto no partido X", provider=mock)
    assert res.blocked is True
    assert res.category == "political"
    assert res.stage == "llm"

def test_refusal_messages():
    assert "senhas" in get_refusal_message("credentials", "pt-br")
    assert "passwords" in get_refusal_message("credentials", "en")
    assert "contraseñas" in get_refusal_message("credentials", "es")
    assert "partilhes" in get_refusal_message("credentials", "pt-pt")
    
    assert "privacidade" in get_refusal_message("health_data", "pt-br")
    assert "privacy" in get_refusal_message("political", "en")

def test_fail_safe():
    # If something crashes, it should return blocked=False (fail-open)
    # We can't easily force a crash in check_credentials_regex without deep mocking, 
    # but we can test the try-except in check_sensitive_data by passing None and forcing an error?
    # Actually, pass an object that raises when .lower() is called
    class Cms:
        def lower(self): raise ValueError("Crash")
        def strip(self): return self
        def __len__(self): return 10
        
    import asyncio
    res = asyncio.run(check_sensitive_data(Cms()))
    assert res.blocked is False
    assert "Critical error" in res.reason
