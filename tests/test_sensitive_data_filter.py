import pytest
from dataclasses import dataclass
from backend.sensitive_data_filter import (
    check_credentials_regex,
    check_sensitive_data,
    get_refusal_message,
    SensitiveDataResult
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
    assert check_credentials_regex("Minha conta \u00e9 1234 5678 1234 5670").blocked is True # Valid Luhn (fake)
    # API Key
    assert check_credentials_regex("Use a chave sk-abc12345678901234567890").blocked is True
    assert check_credentials_regex("Bearer abc123def456").blocked is True
    # Password
    assert check_credentials_regex("senha: 123456").blocked is True
    assert check_credentials_regex("my password is 'secret'").blocked is True
    assert check_credentials_regex("contrase\u00f1a: gato123").blocked is True
    # PIN
    assert check_credentials_regex("o meu pin \u00e9 4321").blocked is True
    assert check_credentials_regex("access code: 9988").blocked is True
    # PEM
    assert check_credentials_regex("-----BEGIN RSA PRIVATE KEY-----").blocked is True

def test_credentials_regex_allowed():
    assert check_credentials_regex("lembrar de comprar pão").blocked is False
    assert check_credentials_regex("senha do meu coração é amor").blocked is True # keyword + value pattern
    assert check_credentials_regex("o PIN do cartão deve ser trocado").blocked is False # concept only, no value

@pytest.mark.asyncio
async def test_sensitive_data_llm_blocked():
    # Political
    mock = MockLLMProvider('{"blocked": true, "reason": "political", "category": "political", "language": "pt-br"}')
    res = await check_sensitive_data("Eu voto no partido X", provider=mock)
    assert res.blocked is True
    assert res.category == "political"

    # Religious
    mock = MockLLMProvider('{"blocked": true, "reason": "religious", "category": "religious", "language": "pt-br"}')
    res = await check_sensitive_data("Minha religião é Y", provider=mock)
    assert res.blocked is True
    assert res.category == "religious"

    # Racial
    mock = MockLLMProvider('{"blocked": true, "reason": "racial", "category": "racial", "language": "pt-br"}')
    res = await check_sensitive_data("De origem étnica Z", provider=mock)
    assert res.blocked is True

@pytest.mark.asyncio
async def test_sensitive_data_allowed_medical():
    mock = MockLLMProvider('{"blocked": false, "reason": "medical allowed", "category": "allowed", "language": "pt-br"}')
    
    # Dental appointment
    res = await check_sensitive_data("Lembrete: consulta no dentista amanhã às 15h", provider=mock)
    assert res.blocked is False
    
    # Medication
    res = await check_sensitive_data("Lembrar tomar medicamento às 8h", provider=mock)
    assert res.blocked is False

def test_refusal_messages():
    assert "senhas" in get_refusal_message("credentials", "pt-br")
    assert "passwords" in get_refusal_message("credentials", "en")
    assert "contraseñas" in get_refusal_message("credentials", "es")
    assert "partilhes" in get_refusal_message("credentials", "pt-pt")
    
    assert "privacidade" in get_refusal_message("health_data", "pt-br")
    assert "privacy" in get_refusal_message("political", "en")
