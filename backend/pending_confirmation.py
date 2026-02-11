"""Detecção de confirmação de oferta pendente (ex.: «Quero sim» após oferta de lembrete a cada 30 min).

Usa Mimo (scope_provider) para analisar o histórico e extrair os parâmetros do cron a criar.
"""

import re
from typing import Any

# Frases curtas que indicam confirmação (pt, es, en)
_CONFIRM_PATTERNS = [
    r"^(sim|s[ií]|yes|s[ií]m)\s*$",
    r"^(quero\s+)?(sim|s[ií])\s*$",
    r"^(ok|okay|pode|puede|can)\s*$",
    r"^(faz|fa[cç]a|manda|envia|do\s+it)\s*$",
    r"^(claro|certeza|certo|combinado|deal)\s*$",
    r"^(confirma|confirmo|confirmado)\s*$",
    r"^(\d)\s*=\s*sim\s*$",  # 1=sim
]


def looks_like_confirmation(content: str) -> bool:
    """True se a mensagem é curta e parece uma confirmação."""
    t = (content or "").strip().lower()
    if not t or len(t) > 50:
        return False
    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, t):
            return True
    return False


async def try_extract_pending_cron(
    scope_provider: Any,
    scope_model: str,
    last_messages: list[dict[str, str]],
    user_message: str,
) -> dict[str, Any] | None:
    """
    Usa Mimo para verificar se o utilizador está a confirmar uma oferta de lembrete.
    Retorna {"every_seconds": N, "message": "..."} ou {"in_seconds": N, "message": "..."} se for confirmação,
    ou None se não for.

    last_messages: [{"role": "user|assistant", "content": "..."}, ...] (mais recente por último)
    """
    if not scope_provider or not scope_model or not last_messages or not user_message:
        return None
    conv_text = "\n".join(
        f"{m['role']}: {m.get('content', '')}"
        for m in last_messages[-6:]
    )
    prompt = f"""Analisa esta conversa. O assistente fez uma oferta para criar um lembrete (ex.: "a cada 30 minutos", "respirar conscientemente").
O utilizador respondeu. É uma CONFIRMAÇÃO dessa oferta?

Conversa:
{conv_text}

Mensagem actual do utilizador: «{user_message[:100]}»

Se for confirmação, responde APENAS numa linha:
CRON_ADD every_seconds=N message="texto"
ou
CRON_ADD in_seconds=N message="texto"

Regras:
- every_seconds: para recorrência (ex.: a cada 30 min = 1800, a cada 1 hora = 3600)
- in_seconds: para lembrete único (ex.: daqui a 5 min = 300)
- message: o texto exacto que o assistente sugeriu (ex.: "respirar conscientemente", "pausa para respirar")
- Se NÃO for confirmação, responde: NA"""

    try:
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=84,
            temperature=0,
        )
        out = (r.content or "").strip()
        if not out or out.upper() == "NA":
            return None
        # Parse CRON_ADD every_seconds=1800 message="respirar conscientemente"
        m = re.search(
            r"CRON_ADD\s+(?:every_seconds=(\d+)|in_seconds=(\d+))\s+message=[\"']([^\"']+)[\"']",
            out,
            re.I,
        )
        if not m:
            m = re.search(
                r"CRON_ADD\s+(?:every_seconds=(\d+)|in_seconds=(\d+))\s+message=(\S+(?:\s+\S+)*)",
                out,
                re.I,
            )
        if m:
            every = m.group(1)
            in_sec = m.group(2)
            msg = (m.group(3) or "").strip().strip('"\'')
            if every and msg:
                return {"every_seconds": int(every), "message": msg}
            if in_sec and msg:
                return {"in_seconds": int(in_sec), "message": msg}
    except Exception:
        pass
    return None
