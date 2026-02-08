"""Parser de comandos: /lembrete, /list, /feito, /filme. Retorna intent estruturado ou None."""

import re
from typing import Any

# Padrões
# /lembrete "texto" em 2 min  |  /lembrete texto daqui a 10 min
RE_LEMBRETE = re.compile(
    r"^/lembrete\s+(.+)$",
    re.I,
)
RE_LEMBRETE_DAQUI = re.compile(r"daqui\s+a\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)
RE_LEMBRETE_EM = re.compile(r"em\s+(\d+)\s*(min|minuto|hora|dia)s?", re.I)

# /list mercado add leite  |  /list pendentes  |  /list
RE_LIST_ADD = re.compile(r"^/list\s+(\S+)\s+add\s+(.+)$", re.I)
RE_LIST_SHOW = re.compile(r"^/list\s+(\S+)\s*$", re.I)
RE_LIST_ALL = re.compile(r"^/list\s*$", re.I)

# /feito 1  |  /feito mercado 1
RE_FEITO_ID = re.compile(r"^/feito\s+(\d+)\s*$", re.I)
RE_FEITO_LIST_ID = re.compile(r"^/feito\s+(\S+)\s+(\d+)\s*$", re.I)

# /filme Nome do Filme
RE_FILME = re.compile(r"^/filme\s+(.+)$", re.I)


def _parse_lembrete_time(text: str) -> dict[str, Any]:
    """Extrai in_seconds ou cron_expr e message do texto do lembrete."""
    text = text.strip()
    text_lower = text.lower()
    # "daqui a 2 min" ou "em 5 minutos" -> extrair número e unidade, resto é a mensagem
    for pattern in (RE_LEMBRETE_DAQUI, RE_LEMBRETE_EM):
        m = pattern.search(text)
        if m:
            n = int(m.group(1))
            unit = (m.group(2) or "").lower()
            if "hora" in unit:
                n *= 3600
            elif "dia" in unit:
                n *= 86400
            else:
                n *= 60  # min
            if n > 0 and n <= 86400 * 7:  # max 7 dias
                # Mensagem = texto sem a parte do tempo
                message = (text[: m.start()] + text[m.end() :]).strip()
                if not message:
                    message = "Lembrete"
                return {"in_seconds": n, "message": message}
    # "todo dia às 9h" simples
    if "todo dia" in text_lower or "todos os dias" in text_lower:
        return {"cron_expr": "0 9 * * *", "message": text}
    # Sem tempo claro: só mensagem (LLM vai tratar)
    return {"message": text}


def parse(raw: str) -> dict[str, Any] | None:
    """
    Parseia a mensagem. Retorna um intent dict ou None.
    Intent: {type: str, ...args}
    """
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None

    # /lembrete ...
    m = RE_LEMBRETE.match(text)
    if m:
        rest = m.group(1).strip()
        if rest:
            intent = _parse_lembrete_time(rest)
            intent["type"] = "lembrete"
            return intent
        return None

    # /list nome add item
    m = RE_LIST_ADD.match(text)
    if m:
        return {"type": "list_add", "list_name": m.group(1).strip(), "item": m.group(2).strip()}

    # /list nome
    m = RE_LIST_SHOW.match(text)
    if m:
        return {"type": "list_show", "list_name": m.group(1).strip()}

    # /list
    if RE_LIST_ALL.match(text):
        return {"type": "list_show", "list_name": None}

    # /feito lista id  ou  /feito id
    m = RE_FEITO_LIST_ID.match(text)
    if m:
        return {"type": "feito", "list_name": m.group(1).strip(), "item_id": int(m.group(2))}
    m = RE_FEITO_ID.match(text)
    if m:
        return {"type": "feito", "list_name": None, "item_id": int(m.group(1))}

    # /filme nome
    m = RE_FILME.match(text)
    if m:
        return {"type": "filme", "nome": m.group(1).strip()}

    return None
