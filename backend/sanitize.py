"""Sanitização de entrada contra injeção (código, SQL, cron, log). Não executa input como código."""

import re
from typing import Any

# Limites razoáveis para conteúdo de utilizador/LLM
MAX_MESSAGE_LEN = 2000
MAX_LIST_NAME_LEN = 128
MAX_ITEM_TEXT_LEN = 512
MAX_EVENT_NAME_LEN = 256
MAX_PAYLOAD_KEYS = 20
MAX_PAYLOAD_DEPTH = 3
MAX_PAYLOAD_VALUE_LEN = 500

# Cron: apenas caracteres seguros (5 campos: min hora dia mês dow)
CRON_SAFE_PATTERN = re.compile(r"^[\d*,\-/\s]+$")
CRON_FIELD_COUNT = 5  # min hour day month dow


def _strip_control(s: str, allow_newline: bool = False) -> str:
    """Remove caracteres de controlo (evita log injection e quebras de formato)."""
    if not s:
        return s
    return "".join(
        c for c in s
        if (allow_newline and (c == "\n" or c == "\t")) or (ord(c) >= 0x20 and ord(c) != 0x7F)
    )


def sanitize_string(
    value: str | None,
    max_len: int = MAX_MESSAGE_LEN,
    allow_newline: bool = False,
) -> str:
    """
    Sanitiza string de utilizador/LLM: remove control chars e limita tamanho.
    Reduz risco de injeção em logs e em conteúdos armazenados.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)[:max_len]
    s = value.strip()
    s = _strip_control(s, allow_newline=allow_newline)
    return s[:max_len] if len(s) > max_len else s


def validate_cron_expr(expr: str | None) -> bool:
    """
    Valida expressão cron: só caracteres seguros e 5 campos.
    Evita injeção em croniter (ex.: strings que causem eval ou path traversal).
    """
    if not expr or not isinstance(expr, str):
        return False
    s = expr.strip()
    if not s or len(s) > 64:
        return False
    if not CRON_SAFE_PATTERN.match(s):
        return False
    parts = s.split()
    return len(parts) == CRON_FIELD_COUNT


def sanitize_payload(
    payload: dict[str, Any] | None,
    max_keys: int = MAX_PAYLOAD_KEYS,
    max_depth: int = MAX_PAYLOAD_DEPTH,
    max_value_len: int = MAX_PAYLOAD_VALUE_LEN,
    _depth: int = 0,
) -> dict[str, Any]:
    """
    Sanitiza payload (ex.: evento): limita chaves, profundidade e tamanho de valores.
    Valores não-string são convertidos para string e truncados.
    """
    if payload is None or _depth > max_depth:
        return {}
    if not isinstance(payload, dict):
        return {}
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(payload.items()):
        if i >= max_keys:
            break
        if not isinstance(k, str) or not k.strip():
            continue
        key = _strip_control(k.strip())[:64]
        if not key:
            continue
        if isinstance(v, dict):
            out[key] = sanitize_payload(v, max_keys, max_depth, max_value_len, _depth + 1)
        elif isinstance(v, str):
            out[key] = sanitize_string(v, max_value_len)
        elif v is None or isinstance(v, (bool, int, float)):
            out[key] = v
        else:
            out[key] = sanitize_string(str(v), max_value_len)
    return out


def clamp_limit(limit: int | None, default: int = 100, maximum: int = 500) -> int:
    """Limita parâmetro numérico (ex.: limit em queries) para evitar abuso."""
    if limit is None:
        return default
    try:
        n = int(limit)
        return max(1, min(maximum, n))
    except (TypeError, ValueError):
        return default
