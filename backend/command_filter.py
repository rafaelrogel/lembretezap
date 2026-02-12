"""Filtragem de comandos: blocklist de padrões perigosos (shell, SQL, path) com logging.

Complementa injection_guard (prompt injection) e sanitize (cron, control chars).
Comandos bloqueados são registados para auditoria (#blocked no God mode).
"""

import json
import re
import time
from pathlib import Path
from typing import Any

_STORE_PATH = Path.home() / ".nanobot" / "security" / "blocked_commands.json"
_MAX_ENTRIES = 500

# Padrões perigosos: shell injection, SQL, path traversal, comandos destrutivos
_BLOCKED_PATTERNS: list[tuple[str, str]] = [
    # Shell / command injection
    (r"\$\([^)]*\)", "shell_substitution"),
    (r"`[^`]*`", "backtick_command"),
    (r"\|\s*(?:rm|cat|wget|curl|nc|bash|sh|python)\b", "pipe_command"),
    (r"&&\s*(?:rm|sudo|chmod|wget|curl)\b", "chain_dangerous"),
    (r";\s*(?:rm|sudo|chmod|wget|curl|nc)\b", "semicolon_command"),
    (r"\brm\s+-rf\s+/", "rm_rf_root"),
    (r"\bsudo\s+", "sudo"),
    (r"\bchmod\s+[0-7]{3,4}\s+", "chmod_octal"),
    (r"\b(?:wget|curl)\s+-[oO]\s+/", "download_to_root"),
    # SQL injection / DDL
    (r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b", "sql_drop"),
    (r"\bDELETE\s+FROM\b", "sql_delete"),
    (r"\bTRUNCATE\b", "sql_truncate"),
    (r"\bINSERT\s+INTO\b", "sql_insert"),
    (r"\bUPDATE\s+\w+\s+SET\b", "sql_update"),
    (r";\s*--\s*$", "sql_comment_injection"),
    # Path traversal
    (r"\.\./\.\./", "path_traversal"),
    (r"/etc/passwd", "path_sensitive"),
    (r"/\.env", "path_env"),
    # Outros
    (r"\beval\s*\(", "eval"),
    (r"\bexec\s*\(", "exec"),
    (r"<script\b", "html_script"),
]

_BLOCKED_RE = re.compile(
    "|".join(f"({p})" for p, _ in _BLOCKED_PATTERNS),
    re.I,
)


def is_blocked(text: str) -> tuple[bool, str]:
    """
    Retorna (True, reason) se a mensagem contém padrões bloqueados.
    Caso contrário (False, "").
    """
    if not text or not text.strip():
        return False, ""
    t = text.strip()
    m = _BLOCKED_RE.search(t)
    if not m:
        return False, ""
    for i, (_, reason) in enumerate(_BLOCKED_PATTERNS):
        if m.group(i + 1) is not None:
            return True, reason
    return True, "pattern_match"


def record_blocked(
    channel: str,
    chat_id: str,
    preview: str,
    reason: str,
) -> None:
    """Regista tentativa de comando bloqueada (para auditoria e #blocked)."""
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries: list[dict] = []
        if _STORE_PATH.exists():
            try:
                entries = json.loads(_STORE_PATH.read_text())
            except Exception:
                entries = []
        ts = int(time.time())
        digits = "".join(c for c in str(chat_id) if c.isdigit())
        client_id = (digits[:5] + "***" + digits[-4:]) if len(digits) >= 9 else (digits or str(chat_id)[:12])
        entries.append({
            "channel": channel,
            "chat_id": client_id,
            "timestamp": ts,
            "reason": reason,
            "preview": (preview or "")[:80],
        })
        if len(entries) > _MAX_ENTRIES:
            entries = entries[-_MAX_ENTRIES:]
        _STORE_PATH.write_text(json.dumps(entries, ensure_ascii=False))
    except Exception:
        pass


def get_blocked_stats() -> list[dict[str, Any]]:
    """
    Agrega tentativas de comandos bloqueados por cliente.
    Para God mode #blocked.
    """
    try:
        if not _STORE_PATH.exists():
            return []
        entries = json.loads(_STORE_PATH.read_text())
    except Exception:
        return []
    by_client: dict[str, dict[str, Any]] = {}
    for e in entries:
        cid = e.get("chat_id", "?")
        ch = e.get("channel", "")
        key = f"{ch}:{cid}"
        if key not in by_client:
            by_client[key] = {"chat_id": cid, "channel": ch, "total": 0, "reasons": {}}
        by_client[key]["total"] += 1
        reason = (e.get("reason") or "unknown")
        by_client[key]["reasons"][reason] = by_client[key]["reasons"].get(reason, 0) + 1
    return sorted(by_client.values(), key=lambda x: -x["total"])
