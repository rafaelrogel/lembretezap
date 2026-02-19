"""Contacto com atendimento ao cliente: detecção e resposta empática."""

import os
import re

# Configurável via env (default: placeholders do utilizador)
ATENDIMENTO_PHONE = os.environ.get("ATENDIMENTO_PHONE", "+55 71 111111111").strip()
ATENDIMENTO_EMAIL = os.environ.get("ATENDIMENTO_EMAIL", "atendimento@exemplo.com").strip()

# Padrões que indicam pedido de contato com atendimento
_ATENDIMENTO_PATTERNS = [
    r"\b(quero|quisesse|preciso|precisaria)\s+(falar|conversar|entrar em contato)\s+(com\s+)?(o\s+)?(atendimento|suporte|humano|pessoa)\b",
    r"\b(atendimento|suporte)\s+(ao\s+)?cliente\b",
    r"\b(falar|fale)\s+com\s+(uma\s+)?(pessoa|humano|atendente)\b",
    r"\bcontato\s+(com\s+)?(o\s+)?atendimento\b",
    r"\b(ligar|ligue)\s+para\s+(mim|mim)\b",
    r"\b(telefone|número)\s+(do\s+)?(atendimento|suporte)\b",
    r"\b(speak|talk)\s+to\s+(a\s+)?(human|person|agent)\b",
]

_ATENDIMENTO_RE = re.compile("|".join(f"({p})" for p in _ATENDIMENTO_PATTERNS), re.I)


def is_atendimento_request(text: str) -> bool:
    """True se o utilizador pede contacto com atendimento ao cliente."""
    return bool(text and _ATENDIMENTO_RE.search(text.strip()))


async def build_atendimento_response(
    user_lang: str,
    provider,
    model: str,
    scope_provider=None,
    scope_model: str | None = None,
) -> str:
    """
    Mimo primeiro (barato, mensagem curta) → fallback DeepSeek → fallback hardcoded.
    """
    contact = f"📞 {ATENDIMENTO_PHONE}\n📧 {ATENDIMENTO_EMAIL}"
    lang_instruction = {
        "pt-PT": "em português de Portugal, caloroso e empático",
        "pt-BR": "em português do Brasil, caloroso e empático",
        "es": "en español, cálido y empático",
        "en": "in English, warm and empathetic",
    }.get(user_lang, "in the user's language, warm and empathetic")
    prompt = f"""O utilizador pediu para falar com o atendimento ao cliente. Gera uma mensagem MUITO curta (1-2 frases no máximo, além dos contactos) que:
1) Seja solidária e empática (reconheça que ele quer ajuda humana)
2) Indique que a equipa vai contactá-lo
3) Inclua estes dados de contacto:
{contact}

Escreve {lang_instruction}. Seja CONCISO: máximo 1-2 frases + contactos. Sem bullet points, texto fluido mas breve."""

    # 1) Mimo (mais barato — mensagem curta)
    if scope_provider and (scope_model or "").strip():
        try:
            r = await scope_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                model=scope_model,
                max_tokens=130,
                temperature=0.6,
            )
            out = (r.content or "").strip()
            if out:
                return out
        except Exception:
            pass  # fallback para DeepSeek

    # 2) DeepSeek (fallback)
    try:
        r = await provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=130,
            temperature=0.6,
        )
        out = (r.content or "").strip()
        if out:
            return out
    except Exception:
        pass

    # 3) Fallback hardcoded (sem LLM)
    fallbacks = {
        "pt-PT": f"Entendo. A nossa equipa vai contactar-te. 📞 {ATENDIMENTO_PHONE} | 📧 {ATENDIMENTO_EMAIL}",
        "pt-BR": f"Entendo. Nossa equipe vai entrar em contato com você. 📞 {ATENDIMENTO_PHONE} | 📧 {ATENDIMENTO_EMAIL}",
        "es": f"Entiendo. Nuestro equipo te contactará. 📞 {ATENDIMENTO_PHONE} | 📧 {ATENDIMENTO_EMAIL}",
        "en": f"I understand. Our team will reach out. 📞 {ATENDIMENTO_PHONE} | 📧 {ATENDIMENTO_EMAIL}",
    }
    return fallbacks.get(user_lang, fallbacks["pt-BR"])

