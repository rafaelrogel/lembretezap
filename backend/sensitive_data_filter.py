"""Sensitive data filter: detect and block LGPD/GDPR sensitive categories and credentials."""

import re
import json
from dataclasses import dataclass
from typing import Optional
from backend.logger import get_logger

logger = get_logger(__name__)

@dataclass
class SensitiveDataResult:
    blocked: bool
    reason: str
    category: str        # e.g. "credentials", "health_data", "political", "allowed", etc.
    stage: str           # "regex", "intent", "llm", or "none"
    detected_language: str  # "pt-br", "pt-pt", "es", "en", "other"

@dataclass  
class CredentialCheckResult:
    blocked: bool
    pattern_matched: str  # e.g. "card_number", "api_key", "password_assignment"
    confidence: str       # "high", "medium"

# Regex patterns for credentials
_RE_CREDENTIALS = {
    # High-confidence: Actual values
    "card_number": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "api_key_explicit": re.compile(r"\b(sk-[a-zA-Z0-9]{20,}|Bearer\s+[a-zA-Z0-9\-\._~+/]+=*)\b", re.I),
    "pem_block": re.compile(r"-----BEGIN [A-Z ]+-----"),
    "ssh_key": re.compile(r"ssh-rsa AAAA[0-9A-Za-z+/]+[=]{0,3}"),
    
    # Medium-confidence: Likely assignments (requires : or =)
    "api_key_assignment": re.compile(r"\b(api_key|token|secret)[=: ]+[a-zA-Z0-9_\-]{8,}\b", re.I),
    "password_assignment": re.compile(r"\b(password|senha|contraseña|pwd|acesso|login)[=:]\s*\S+", re.I),
    "password_is": re.compile(r"\b(senha|password|contraseña).{0,25}\s+(?:é|is|es)\s+\S+", re.I),
    "numeric_pin": re.compile(r"\b(pin|codigo|código|access|acesso|door|lock|home|segurança|seguridad|security|code)[^0-9]{0,5}\b\d{4,8}\b", re.I),
}

# Heuristics for safe intents (reminding to manage credentials without providing them)
_SAFE_INTENT_KEYWORDS = (
    # PT
    r"trocar", r"mudar", r"redefinir", r"cancelar", r"renovar", r"revogar", r"atualizar", r"remover", r"alterar",
    # EN
    r"change", r"rotate", r"reset", r"cancel", r"renew", r"revoke", r"update", r"remove", r"alter",
    # ES
    r"cambiar", r"reestablecer", r"cancelar", r"renovar", r"revocar", r"actualizar", r"eliminar", r"modificar",
)
_RE_SAFE_INTENT = re.compile(r"\b(" + "|".join(_SAFE_INTENT_KEYWORDS) + r")\b", re.I)

def is_safe_intent_reminder(message: str) -> bool:
    """True if message seems to be about managing a credential without providing it."""
    m = message.lower().strip()
    # 1. Must have a safe verb
    if not _RE_SAFE_INTENT.search(m):
        return False
        
    # 2. Must mention a credential keyword
    credential_keywords = r"(senha|password|contraseña|api|token|chave|key|clave|codigo|código|pin)"
    if not re.search(credential_keywords, m):
        return False

    # 3. Must NOT have obvious assignment-like patterns
    if any(pat.search(message) for pat in (_RE_CREDENTIALS["api_key_assignment"], 
                                              _RE_CREDENTIALS["password_assignment"],
                                              _RE_CREDENTIALS["password_is"])):
        return False
        
    # 4. Must NOT have "para X" or "to X" or "a X" followed by a number/secret
    if re.search(r"\b(para|to|a|is|é|es)\b\s*\d+", m):
        return False

    return True

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

    # 1. High confidence: Cards (with Luhn)
    for m in _RE_CREDENTIALS["card_number"].finditer(message):
        num = m.group(0)
        if _is_luhn_valid(num):
            return CredentialCheckResult(blocked=True, pattern_matched="card_number", confidence="high")

    # 2. High confidence: Explicit keys
    if _RE_CREDENTIALS["api_key_explicit"].search(message) or _RE_CREDENTIALS["pem_block"].search(message) or _RE_CREDENTIALS["ssh_key"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="explicit_secret", confidence="high")

    # 3. Medium confidence: Assignments
    if _RE_CREDENTIALS["api_key_assignment"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="api_key_assignment", confidence="medium")
    
    if _RE_CREDENTIALS["password_assignment"].search(message) or _RE_CREDENTIALS["password_is"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="password_assignment", confidence="medium")

    # 4. Numeric PINs in context
    if _RE_CREDENTIALS["numeric_pin"].search(message):
        return CredentialCheckResult(blocked=True, pattern_matched="numeric_pin", confidence="medium")

    return CredentialCheckResult(blocked=False, pattern_matched="", confidence="")

_PROMPT_SENSITIVE = """Analise se a mensagem do usuário contém dados pessoais sensíveis ou compartilhamento de credenciais.

CATEGORIAS BLOQUEADAS (blocked=true):
1. Origem racial, opiniões políticas, convicções religiosas, filiação sindical.
2. Dados genéticos, biométricos ou de saúde (exceto consultas/medicações).
3. Vida/orientação sexual.
4. CREDENCIAIS EXPLICITAS: Bloqueie se o usuário estiver fornecendo uma senha, token, chave API ou código de acesso real (ex: "minha senha é 123", "token: sk-abc").

EXCEÇÕES PERMITIDAS (blocked=false):
- Gestão de segurança (ex: "lembre-me de trocar a senha", "cancelar API", "renovar token"). Falar SOBRE a existência de uma senha/API sem revelar o valor é PERMITIDO.
- Consultas médicas e horários de medicação.

Responda APENAS com JSON:
{{
  "blocked": true/false,
  "reason": "motivo",
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
    """Two-stage detection: Regex then LLM. Fail-safe design."""
    try:
        if not message or len(message.strip()) < 2:
            return SensitiveDataResult(blocked=False, reason="", category="allowed", stage="none", detected_language=user_language)

        # Stage 1: Fast Regex check
        creds = check_credentials_regex(message)
        
        # If high confidence block -> Block immediately
        if creds.blocked and creds.confidence == "high":
            logger.warning("sensitive_data_blocked", extra={"extra": {
                "action": "SENSITIVE_DATA_BLOCKED",
                "category": "credentials",
                "stage": "regex",
                "reason": f"High confidence match: {creds.pattern_matched}"
            }})
            return SensitiveDataResult(
                blocked=True,
                reason=f"High confidence match: {creds.pattern_matched}",
                category="credentials",
                stage="regex",
                detected_language=user_language
            )

        # Optimization: Safe Intent Heuristics
        if is_safe_intent_reminder(message):
             return SensitiveDataResult(
                blocked=False,
                reason="Safe management intent detected",
                category="allowed",
                stage="intent",
                detected_language=user_language
            )

        # If medium confidence regex -> Wait for LLM or block if no LLM
        if creds.blocked and creds.confidence == "medium":
            if provider is None:
                logger.warning("sensitive_data_blocked", extra={"extra": {
                    "action": "SENSITIVE_DATA_BLOCKED",
                    "category": "credentials",
                    "stage": "regex",
                    "reason": f"Medium confidence match (no LLM): {creds.pattern_matched}"
                }})
                return SensitiveDataResult(
                    blocked=True,
                    reason=f"Medium confidence match (no LLM): {creds.pattern_matched}",
                    category="credentials",
                    stage="regex",
                    detected_language=user_language
                )
            # Continue to LLM for final word

        # Stage 2: LLM
        if provider is None:
            return SensitiveDataResult(blocked=False, reason="", category="allowed", stage="none", detected_language=user_language)

        prompt = _PROMPT_SENSITIVE.format(message=message.strip()[:1000])
        response = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            model=model,
            max_tokens=200,
            temperature=0,
        )
        if not response or not response.content:
            return SensitiveDataResult(blocked=False, reason="No LLM response", category="allowed", stage="none", detected_language=user_language)

        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        
        data = json.loads(raw)
        res_blocked = data.get("blocked", False)
        if res_blocked:
            logger.warning("sensitive_data_blocked", extra={"extra": {
                "action": "SENSITIVE_DATA_BLOCKED",
                "category": data.get("category", "allowed"),
                "stage": "llm",
                "reason": data.get("reason", "")
            }})
            
        return SensitiveDataResult(
            blocked=res_blocked,
            reason=data.get("reason", ""),
            category=data.get("category", "allowed"),
            stage="llm",
            detected_language=data.get("language", user_language)
        )
    except Exception as e:
        logger.error("sensitive_data_filter_error", extra={"extra": {"error": str(e)}})
        # FAIL-SAFE: If filter crashes, DO NOT block the user.
        return SensitiveDataResult(blocked=False, reason=f"Critical error: {e}", category="allowed", stage="none", detected_language=user_language)

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
        return "⚠️ Por privacidad, no puedo guardar ese tipo de información pessoal sensível. Si necesitas un recordatorio médico (consulta, medicación), puedes crearlo normalmente."
    elif "en" in lang:
        if category == "credentials":
            return "⚠️ For your security, I cannot store that type of data. Never share passwords, codes or access keys with bots."
        return "⚠️ For your privacy, I cannot store that type of sensitive personal information. Medical reminders (appointments, medication times) are always allowed."
    else: # Default pt-br
        if category == "credentials":
            return "⚠️ Por segurança, não posso registrar esse tipo de dado. Nunca compartilhe senhas, códigos ou chaves de acesso com bots."
        return "⚠️ Por privacidade, não posso guardar esse tipo de informação pessoal sensível. Se precisar de um lembrete médico (consulta, medicação), pode criar normalmente."
