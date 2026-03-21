"""Sensitive data filter: detect and block LGPD/GDPR sensitive categories and credentials."""

import re
import json
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class SensitiveDataResult:
    blocked: bool
    reason: str
    category: str        # e.g. "credentials", "health_data", "political", "allowed", etc.
    stage: str           # "regex", "llm", or "none"
    detected_language: str  # "pt-br", "pt-pt", "es", "en", "other"

@dataclass  
class CredentialCheckResult:
    blocked: bool
    pattern_matched: str  # e.g. "card_number", "api_key", "password_keyword"
    confidence: str       # "high", "medium"

# Regex patterns for credentials
_RE_CREDENTIALS = {
    "card_number": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "api_key": re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9\-\._~+/]+=*|api_key[=: ]+[a-zA-Z0-9_\-]+|token[=: ]+[a-zA-Z0-9_\-]+)\b", re.I),
    "password_keyword": re.compile(r"\b(password|senha|contraseña|pass|pwd|mot de passe|Passwort|acesso|login)[=: ]+\S+", re.I),
    "pem_block": re.compile(r"-----BEGIN [A-Z ]+-----"),
    "numeric_pin": re.compile(r"\b(pin|codigo|código|access|acesso|door|lock|home|segurança|seguridad|security|code)[^0-9]{0,10}\b\d{4,8}\b", re.I),
    "ssh_key": re.compile(r"ssh-rsa AAAA[0-9A-Za-z+/]+[=]{0,3}"),
}

def _is_luhn_valid(number: str) -> bool:
    """Check if a string of digits passes the Luhn algorithm."""
    digits = [int(d) for d in re.sub(r"\D", "", number)]
    if not digits:
        return False
    checksum = digits[-1]
    payload = digits[:-1][::-1]
    total = checksum
    for i, d in enumerate(payload):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0

def check_credentials_regex(message: str) -> CredentialCheckResult:
    """Fast-check for obvious credential patterns."""
    if not message or len(message.strip()) < 4:
        return CredentialCheckResult(blocked=False, pattern_matched="", confidence="")

    # 1. Card numbers (with Luhn validation)
    for m in _RE_CREDENTIALS["card_number"].finditer(message):
        num = m.group(0)
        if _is_luhn_valid(num):
            return CredentialCheckResult(blocked=True, pattern_matched="card_number", confidence="high")

    # 2. API keys and tokens
    if _RE_CREDENTIALS["api_key"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="api_key", confidence="high")

    # 3. Password keywords with values
    if _RE_CREDENTIALS["password_keyword"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="password_keyword", confidence="high")

    # 4. PEM blocks and SSH keys
    if _RE_CREDENTIALS["pem_block"].search(message) or _RE_CREDENTIALS["ssh_key"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="secure_block", confidence="high")

    # 5. Numeric PINs in context
    if _RE_CREDENTIALS["numeric_pin"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="numeric_pin", confidence="high")

    return CredentialCheckResult(blocked=False, pattern_matched="", confidence="")

_PROMPT_SENSITIVE = """Analise se a mensagem do usuário (que se destina a ser um lembrete ou item de lista) contém dados pessoais sensíveis que NÃO devem ser armazenados de acordo com o RGPD/LGPD ou contém credenciais.

CATEGORIAS BLOQUEADAS (blocked=true):
1. Origem racial ou étnica.
2. Opiniões políticas ou filiação partidária.
3. Convicções religiosas ou filosóficas.
4. Filiação sindical ou a organizações políticas/religiosas.
5. Dados genéticos ou biométricos.
6. Dados de saúde (EXCETO o que for permitido abaixo).
7. Vida sexual ou orientação sexual.
8. Credenciais, senhas, PINs, tokens, chaves API.

EXCEÇÕES PERMITIDAS (blocked=false):
- Lembretes de CONSULTAS MÉDICAS (ex: "dentista amanhã 15h", "médico sexta").
- Lembretes de HORÁRIOS DE MEDICAÇÃO (ex: "tomar paracetamol 8h", "insulina 7am").

Responda APENAS com um JSON neste formato:
{{
  "blocked": true/false,
  "reason": "breve explicação em português",
  "category": "credentials" | "health_data" | "political" | "religious" | "racial" | "sexual" | "allowed",
  "language": "pt-br" | "pt-pt" | "es" | "en" | "other"
}}

Mensagem: "{message}"
"""

async def check_sensitive_data(
    message: str,
    provider=None,
    model: str | None = None,
    user_language: str = "pt-br"
) -> SensitiveDataResult:
    """Two-stage detection: Regex then LLM."""
    # Stage 1: Regex
    creds = check_credentials_regex(message)
    if creds.blocked:
        return SensitiveDataResult(
            blocked=True,
            reason=f"Pattern matched: {creds.pattern_matched}",
            category="credentials",
            stage="regex",
            detected_language=user_language
        )

    # Stage 2: LLM
    if provider is None:
        return SensitiveDataResult(blocked=False, reason="", category="allowed", stage="none", detected_language=user_language)

    try:
        prompt = _PROMPT_SENSITIVE.format(message=message.strip()[:1000])
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            max_tokens=200,
            temperature=0,
        )
        if not response or not response.content:
            return SensitiveDataResult(blocked=False, reason="No response", category="allowed", stage="none", detected_language=user_language)

        # Cleanup JSON response
        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        data = json.loads(raw)
        return SensitiveDataResult(
            blocked=data.get("blocked", False),
            reason=data.get("reason", ""),
            category=data.get("category", "allowed"),
            stage="llm",
            detected_language=data.get("language", user_language)
        )
    except Exception as e:
        logger.warning(f"Sensitive data LLM check failed: {e}")
        return SensitiveDataResult(blocked=False, reason=str(e), category="allowed", stage="none", detected_language=user_language)

def get_refusal_message(category: str, language: str) -> str:
    """Return localized refusal message."""
    lang = (language or "pt-br").lower()
    if "pt-pt" in lang:
        if category == "credentials":
            return "⚠️ Por segurança, não posso registar esse tipo de dado. Nunca partilhes senhas, códigos ou chaves de acesso com bots."
        return "⚠️ Por privacidade, não posso guardar esse tipo de informação pessoal sensível. Se precisares de um lembrete médico (consulta, medicação), podes criá-lo normalmente."
    elif "es" in lang:
        if category == "credentials":
            return "⚠️ Por seguridad, no puedo registrar ese tipo de dato. Nunca compartas contraseñas, códigos o claves de acceso con bots."
        return "⚠️ Por privacidad, no puedo guardar ese tipo de información personal sensible. Si necesitas un recordatorio médico (consulta, medicación), puedes crearlo normalmente."
    elif "en" in lang:
        if category == "credentials":
            return "⚠️ For your security, I cannot store that type of data. Never share passwords, codes or access keys with bots."
        return "⚠️ For your privacy, I cannot store that type of sensitive personal information. Medical reminders (appointments, medication times) are always allowed."
    else: # Default pt-br
        if category == "credentials":
            return "⚠️ Por segurança, não posso registrar esse tipo de dado. Nunca compartilhe senhas, códigos ou chaves de acesso com bots."
        return "⚠️ Por privacidade, não posso guardar esse tipo de informação pessoal sensível. Se precisar de um lembrete médico (consulta, medicação), pode criar normalmente."
