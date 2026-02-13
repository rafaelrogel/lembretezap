"""Rate-limit/lockout para tentativas de senha errada no God Mode.

Evita brute force silencioso: após N tentativas erradas (#<senha_incorreta>),
o chat fica bloqueado por X minutos. Persistido em disco para sobreviver a restarts.
"""

import json
import os
import threading
import time
from pathlib import Path

from loguru import logger

# chat_id -> {"count": int, "first_ts": float, "locked_until": float}
_lockout_state: dict[str, dict] = {}
_LOCK = threading.Lock()
_LOADED = False

_STORE_PATH = Path(os.environ.get("ZAPISTA_DATA", "").strip() or str(Path.home() / ".zapista")) / "security" / "god_mode_lockout.json"
_MAX_ATTEMPTS = int(os.environ.get("GOD_MODE_MAX_ATTEMPTS", "5"))
_LOCKOUT_SECONDS = int(os.environ.get("GOD_MODE_LOCKOUT_MINUTES", "15")) * 60
_WINDOW_SECONDS = 60 * 15  # janela para contar tentativas (15 min); após isso, count reseta


def _load_state() -> None:
    """Carrega estado de disco uma vez (thread-safe)."""
    global _LOADED
    if _LOADED or not _STORE_PATH.exists():
        return
    try:
        with _LOCK:
            if _LOADED:
                return
            data = json.loads(_STORE_PATH.read_text())
            now = time.time()
            for cid, entry in (data.get("chats") or {}).items():
                locked_until = entry.get("locked_until", 0)
                if locked_until > now:
                    _lockout_state[cid] = {
                        "count": entry.get("count", _MAX_ATTEMPTS),
                        "first_ts": entry.get("first_ts", now),
                        "locked_until": locked_until,
                    }
                elif now - entry.get("first_ts", 0) < _WINDOW_SECONDS:
                    _lockout_state[cid] = {
                        "count": entry.get("count", 0),
                        "first_ts": entry.get("first_ts", now),
                        "locked_until": 0,
                    }
            _LOADED = True
    except Exception:
        _LOADED = True


def _save_state() -> None:
    """Persiste estado para disco."""
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        with _LOCK:
            to_save = {
                cid: entry for cid, entry in _lockout_state.items()
                if entry.get("locked_until", 0) > now or now - entry.get("first_ts", 0) < _WINDOW_SECONDS
            }
        _STORE_PATH.write_text(json.dumps({"chats": to_save, "updated": int(now)}))
    except Exception:
        pass


def is_locked_out(chat_id: str) -> bool:
    """True se este chat está bloqueado por tentativas de senha errada."""
    _load_state()
    cid = str(chat_id)
    with _LOCK:
        entry = _lockout_state.get(cid)
        if not entry:
            return False
        now = time.time()
        locked_until = entry.get("locked_until", 0)
        if locked_until > now:
            return True
        if now - entry.get("first_ts", 0) > _WINDOW_SECONDS:
            del _lockout_state[cid]
            return False
        return False


def record_failed_attempt(chat_id: str) -> None:
    """Regista uma tentativa de senha errada. Se atingir o limite, bloqueia o chat."""
    _load_state()
    cid = str(chat_id)
    now = time.time()
    with _LOCK:
        entry = _lockout_state.get(cid)
        if not entry:
            entry = {"count": 0, "first_ts": now, "locked_until": 0}
            _lockout_state[cid] = entry
        if entry.get("locked_until", 0) > now:
            return  # já bloqueado
        if now - entry.get("first_ts", 0) > _WINDOW_SECONDS:
            entry["count"] = 0
            entry["first_ts"] = now
        entry["count"] = entry.get("count", 0) + 1
        if entry["count"] >= _MAX_ATTEMPTS:
            entry["locked_until"] = now + _LOCKOUT_SECONDS
            logger.warning(
                "god_mode_lockout chat_id={} attempts={} locked_until_ts={}",
                cid[:12] + "***" if len(cid) > 12 else "***",
                entry["count"],
                int(entry["locked_until"]),
            )
    _save_state()


def clear_failed_attempts(chat_id: str) -> None:
    """Limpa tentativas (chamar após login com sucesso)."""
    cid = str(chat_id)
    with _LOCK:
        if cid in _lockout_state:
            del _lockout_state[cid]
    _save_state()


def get_lockout_stats() -> list[dict]:
    """Lista chats bloqueados ou com tentativas recentes (para #lockout)."""
    _load_state()
    now = time.time()
    with _LOCK:
        result = []
        for cid, entry in _lockout_state.items():
            locked_until = entry.get("locked_until", 0)
            count = entry.get("count", 0)
            first_ts = entry.get("first_ts", 0)
            mask = (cid[:8] + "***" + cid[-4:]) if len(cid) > 12 else cid[:12] + "***"
            if locked_until > now:
                remaining = int(locked_until - now)
                result.append({
                    "chat_id": mask,
                    "status": "bloqueado",
                    "attempts": count,
                    "remaining_sec": remaining,
                })
            elif now - first_ts < _WINDOW_SECONDS and count > 0:
                result.append({
                    "chat_id": mask,
                    "status": "tentativas",
                    "attempts": count,
                    "remaining_sec": None,
                })
        return result
