"""Lista extra de números autorizados (adicionados via #add no god-mode).

Persistida em allowed_extra.json no data dir. Combinada com config allow_from em is_allowed().
"""

import json
from pathlib import Path

from nanobot.config.loader import get_data_dir

_FILENAME = "allowed_extra.json"


def _path() -> Path:
    return get_data_dir() / _FILENAME


def _load() -> list[str]:
    p = _path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries: list[str]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entries, ensure_ascii=False, indent=0), encoding="utf-8")


def _normalize(phone: str) -> str:
    """Apenas dígitos."""
    return "".join(c for c in str(phone or "") if c.isdigit())


def get_extra_allowed_list() -> list[str]:
    """Lista de números adicionados via #add (só dígitos)."""
    return _load()


def add_extra_allowed(phone: str) -> bool:
    """Adiciona número à lista. Retorna True se foi adicionado (ainda não estava)."""
    digits = _normalize(phone)
    if not digits:
        return False
    entries = _load()
    if digits in entries:
        return False
    entries.append(digits)
    _save(entries)
    return True


def remove_extra_allowed(phone: str) -> bool:
    """Remove número da lista. Retorna True se foi removido."""
    digits = _normalize(phone)
    if not digits:
        return False
    entries = _load()
    if digits not in entries:
        return False
    entries.remove(digits)
    _save(entries)
    return True
