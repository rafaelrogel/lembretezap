"""
Métricas do servidor para #server (god-mode): snapshot atual + histórico N dias.
Usado para detectar tendências: vazamento RAM, disco a encher, cron atrasado, etc.
"""

import json
import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Retenção padrão de histórico (dias)
DEFAULT_HISTORY_DAYS = 14


def _metrics_path() -> Path:
    data_dir = Path(os.environ.get("ZAPISTA_DATA", "").strip() or str(Path.home() / ".zapista"))
    return data_dir / "server_metrics.json"


def _load_metrics() -> dict[str, Any]:
    path = _metrics_path()
    if not path.exists():
        return {"snapshots": {}, "daily": {}, "today_events": {}, "last_pid": None, "last_create_time": None}
    try:
        data = json.loads(path.read_text())
        return data
    except Exception:
        return {"snapshots": {}, "daily": {}, "today_events": {}, "last_pid": None, "last_create_time": None}


def _save_metrics(data: dict[str, Any]) -> None:
    path = _metrics_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def record_event(event_type: str) -> None:
    """Regista um evento (whatsapp_skipped, unknown_channel, bridge_reconnect)."""
    today = date.today().isoformat()
    data = _load_metrics()
    events = data.setdefault("today_events", {})
    if events.get("_date") != today:
        events.clear()
        events["_date"] = today
    events[event_type] = events.get(event_type, 0) + 1
    _save_metrics(data)


def record_snapshot(
    *,
    cron_store_path: Path | None = None,
    data_dir: Path | None = None,
    bridge_connected: bool | None = None,
) -> dict[str, Any] | None:
    """
    Regista um snapshot das métricas atuais. Chamado periodicamente ou no #server.
    Retorna o snapshot registado.
    """
    try:
        import psutil
    except ImportError:
        return None

    today = date.today().isoformat()
    data = _load_metrics()

    # Snapshot atual
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    # Disco: raiz do drive onde está o data_dir (Windows: C:\, Linux: /)
    disk_root = "/"
    if os.name == "nt":
        disk_root = "C:\\"
        if data_dir:
            parts = Path(data_dir).resolve().parts
            if parts and len(parts[0]) <= 2 and ":" in str(parts[0]):
                disk_root = parts[0] + "\\"
    try:
        disk = psutil.disk_usage(disk_root)
    except Exception:
        disk = type("Disk", (), {"percent": 0, "free": 0})()
    load = (0.0, 0.0, 0.0)
    try:
        load = os.getloadavg()
    except (AttributeError, OSError):
        if hasattr(psutil, "getloadavg"):
            try:
                load = psutil.getloadavg()
            except Exception:
                pass

    cpu_pct = 0.0
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)
    except Exception:
        pass

    # Tamanho pasta de dados
    data_mb = 0
    if data_dir and data_dir.exists():
        try:
            data_mb = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file()) / (1024 * 1024)
        except Exception:
            pass

    proc = psutil.Process()
    create_time = proc.create_time()
    gateway_uptime_s = time.time() - create_time

    # Cron
    cron_jobs = 0
    cron_delayed_60s = 0
    if cron_store_path and cron_store_path.exists():
        try:
            jdata = json.loads(cron_store_path.read_text())
            now_ms = int(time.time() * 1000)
            for j in jdata.get("jobs", []):
                if j.get("enabled", True):
                    cron_jobs += 1
                    nr = (j.get("state") or {}).get("nextRunAtMs")
                    if nr and nr < now_ms - 60_000:
                        cron_delayed_60s += 1
        except Exception:
            pass

    disk_total_mb = round(disk.total / (1024 * 1024), 1) if hasattr(disk, "total") and disk.total else 0
    snapshot = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ram_pct": round(mem.percent, 1),
        "ram_available_mb": round(mem.available / (1024 * 1024), 1),
        "swap_used_mb": round(swap.used / (1024 * 1024), 1),
        "swap_total_mb": round(swap.total / (1024 * 1024), 1),
        "cpu_pct": round(cpu_pct, 1),
        "load_1m": round(load[0], 2),
        "disk_pct": round(disk.percent, 1),
        "disk_free_mb": round(disk.free / (1024 * 1024), 1),
        "disk_total_mb": disk_total_mb,
        "data_dir_mb": round(data_mb, 1),
        "gateway_uptime_s": int(gateway_uptime_s),
        "bridge_connected": bridge_connected,
        "cron_jobs": cron_jobs,
        "cron_delayed_60s": cron_delayed_60s,
        "pid": proc.pid,
        "create_time": create_time,
    }

    snapshots = data.setdefault("snapshots", {})
    if today not in snapshots:
        snapshots[today] = []
    snapshots[today].append(snapshot)
    # Manter no máx 96 snapshots por dia (a cada 15 min)
    snapshots[today] = snapshots[today][-96:]

    # Agregar no daily
    daily = data.setdefault("daily", {})
    if today not in daily:
        daily[today] = {
            "ram_max": 0,
            "load_max": 0,
            "load_spikes": 0,
            "disk_mb": 0,
            "cron_jobs": 0,
            "cron_delayed_60s_max": 0,
            "gateway_restarts": 0,
            "bridge_reconnects": 0,
        }

    d = daily[today]
    d["ram_max"] = max(d.get("ram_max", 0), snapshot["ram_pct"])
    d["load_max"] = max(d.get("load_max", 0), snapshot["load_1m"])
    if snapshot["load_1m"] > 1.5:
        d["load_spikes"] = d.get("load_spikes", 0) + 1
    d["disk_mb"] = snapshot["data_dir_mb"]
    d["cron_jobs"] = snapshot["cron_jobs"]
    d["cron_delayed_60s_max"] = max(d.get("cron_delayed_60s_max", 0), snapshot["cron_delayed_60s"])

    # Eventos de hoje (whatsapp_skipped, unknown_channel)
    events = data.get("today_events", {})
    if events.get("_date") == today:
        d["whatsapp_skipped"] = events.get("whatsapp_skipped", 0)
        d["unknown_channel"] = events.get("unknown_channel", 0)
    d["bridge_reconnects"] = events.get("bridge_reconnect", 0)

    # Detetar restart do gateway
    last_pid = data.get("last_pid")
    last_create = data.get("last_create_time")
    if last_pid is not None and last_create is not None:
        if create_time > last_create + 60:  # novo processo (restart)
            d["gateway_restarts"] = d.get("gateway_restarts", 0) + 1
    data["last_pid"] = proc.pid
    data["last_create_time"] = create_time

    # Purge dias antigos
    cutoff = date.today() - timedelta(days=DEFAULT_HISTORY_DAYS)
    for k in list(snapshots.keys()):
        try:
            if datetime.fromisoformat(k).date() < cutoff:
                del snapshots[k]
                if k in daily:
                    del daily[k]
        except Exception:
            pass

    _save_metrics(data)
    return snapshot


def get_historical(days: int = 7) -> list[dict[str, Any]]:
    """Retorna agregados diários dos últimos N dias."""
    data = _load_metrics()
    daily = data.get("daily", {})
    today = date.today()
    result = []
    for i in range(days):
        d = today - timedelta(days=i)
        key = d.isoformat()
        if key in daily:
            rec = dict(daily[key])
            rec["date"] = key
            result.append(rec)
        else:
            result.append({"date": key, "ram_max": 0, "load_max": 0, "load_spikes": 0, "disk_mb": 0})
    return list(reversed(result))
