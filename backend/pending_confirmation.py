"""Detecção de confirmação ou resposta com tempo após «Quando quer o lembrete?».

- Confirmação: «Quero sim», «ok» → Mimo extrai params do contexto.
- Resposta com tempo: «a cada 30 min», «todo dia às 8h» → Mimo extrai lembrete (msg anterior) + tempo.
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

# Resposta com tempo explícito (fallback: não deixar para o agente inferir)
_TIME_RESPONSE_PATTERNS = (
    r"a\s+cada\s+\d+\s*(min|minuto|hora|dia)",
    r"every\s+\d+\s*(min|hour|day)",
    r"em\s+\d+\s*(min|minuto|hora|dia)",
    r"daqui\s+a\s+\d+",
    r"(?:todo\s+dia|diariamente)\s+(?:às?|as)?\s*\d+",
    r"toda\s+(?:segunda|terça|quarta|quinta|sexta|sábado|domingo)",
    r"todos?\s+os?\s+dias?\s+(?:às?|as)?\s*\d+",
    r"amanh[ãa]\s+(?:às?|as)?\s*\d+",
    r"\d{1,2}\s*h\b",
    r"\d{1,2}:\d{2}",
    r"(?:segunda|ter[cç]a|quarta|quinta|sexta|s[aá]bado|domingo)\s+\d{1,2}\s*h",
)


def looks_like_confirmation(content: str) -> bool:
    """True se a mensagem é curta e parece uma confirmação."""
    t = (content or "").strip().lower()
    if not t or len(t) > 50:
        return False
    for pat in _CONFIRM_PATTERNS:
        if re.search(pat, t):
            return True
    return False


def looks_like_time_response(content: str) -> bool:
    """True se a mensagem parece especificação de tempo (a cada 30 min, todo dia 8h, etc)."""
    t = (content or "").strip()
    if not t or len(t) > 80:
        return False
    tl = t.lower()
    for pat in _TIME_RESPONSE_PATTERNS:
        if re.search(pat, tl, re.I):
            return True
    return False


def last_assistant_asked_when(last_assistant: str) -> bool:
    """True se a última mensagem do assistente foi a pergunta «Quando quer o lembrete?»."""
    if not last_assistant or len(last_assistant.strip()) < 10:
        return False
    t = last_assistant.strip().lower()
    return (
        "quando" in t and ("lembrete" in t or "reminder" in t or "recordatorio" in t or "recordatório" in t)
    ) or ("when" in t and "reminder" in t)


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


async def try_extract_time_response_cron(
    scope_provider: Any,
    scope_model: str,
    last_messages: list[dict[str, str]],
    user_message: str,
) -> dict[str, Any] | None:
    """
    Usuário respondeu com tempo explícito («a cada 30 min», «todo dia às 8h») à pergunta «Quando quer o lembrete?».
    Mimo extrai: lembrete da mensagem anterior do usuário + tempo da mensagem atual.
    Retorna {"every_seconds": N} ou {"in_seconds": N} ou {"cron_expr": "..."} + message.
    """
    if not scope_provider or not scope_model or not last_messages or not user_message:
        return None
    conv_text = "\n".join(
        f"{m['role']}: {m.get('content', '')}"
        for m in last_messages[-6:]
    )
    prompt = f"""O assistente perguntou «Quando você quer o lembrete?». O utilizador respondeu com uma data/hora ou frequência.

Conversa:
{conv_text}

Mensagem actual do utilizador: «{user_message[:120]}»

Extrai da conversa:
1) O TEXTO do lembrete (da mensagem anterior do utilizador, ex: "beber água", "tomar remédio")
2) O TEMPO que o utilizador especificou agora

Responde APENAS numa linha no formato:
CRON_ADD every_seconds=N message="texto"
ou
CRON_ADD in_seconds=N message="texto"
ou
CRON_ADD cron_expr="0 9 * * *" message="texto"

Regras:
- every_seconds: a cada N segundos (30 min=1800, 1 hora=3600, 2 horas=7200)
- in_seconds: daqui a N segundos (5 min=300, 1 hora=3600)
- cron_expr: 5 campos (min hora dia mês dia-semana). Ex: "0 9 * * *" = todo dia 9h, "0 10 * * 1" = segundas 10h
- Se não conseguir extrair, responde: NA"""

    try:
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=120,
            temperature=0,
        )
        out = (r.content or "").strip()
        if not out or out.upper() == "NA":
            return None
        # CRON_ADD every_seconds=1800 message="texto" ou in_seconds=300 ou cron_expr="0 9 * * *"
        for pat in [
            r"CRON_ADD\s+every_seconds=(\d+)\s+message=[\"']([^\"']+)[\"']",
            r"CRON_ADD\s+in_seconds=(\d+)\s+message=[\"']([^\"']+)[\"']",
            r"CRON_ADD\s+cron_expr=[\"']([^\"']+)[\"']\s+message=[\"']([^\"']+)[\"']",
            r"CRON_ADD\s+every_seconds=(\d+)\s+message=(\S+(?:\s+\S+)*)",
            r"CRON_ADD\s+in_seconds=(\d+)\s+message=(\S+(?:\s+\S+)*)",
        ]:
            m = re.search(pat, out, re.I)
            if m:
                if "every_seconds" in pat.lower():
                    return {"every_seconds": int(m.group(1)), "message": (m.group(2) or "").strip().strip('"\'')}
                if "in_seconds" in pat.lower():
                    return {"in_seconds": int(m.group(1)), "message": (m.group(2) or "").strip().strip('"\'')}
                if "cron_expr" in pat.lower():
                    return {"cron_expr": (m.group(1) or "").strip(), "message": (m.group(2) or "").strip().strip('"\'')}
    except Exception:
        pass
    return None
