"""Métricas de uso de tokens por provedor (DeepSeek, Mimo). Para #ai admin.

Registo via record_usage() (chamar do provider após cada completion).
Resumo por dia e últimos 7 dias com custo estimado.
Preços: DeepSeek https://api-docs.deepseek.com/quick_start/pricing/
        Mimo (MiMo-V2-Flash): input $0.09/1M, output $0.29/1M (Xiaomi/OpenRouter).
"""

import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Preços por 1M tokens (USD). DeepSeek: cache miss input; não distinguimos cache hit.
PRICE_PER_1M = {
    "deepseek": {"input": 0.28, "output": 0.42},
    "mimo": {"input": 0.09, "output": 0.29},
}

# Ficheiro de persistência (env ou default)
def _store_path() -> Path:
    p = os.environ.get("TOKEN_USAGE_FILE", "").strip()
    if p:
        return Path(p)
    return Path.home() / ".zapista" / "token_usage.json"

_LOCK = threading.Lock()
_MAX_DAYS_KEPT = 8


def _derive_provider(model: str) -> str:
    """De model string devolve 'deepseek', 'mimo' ou 'other'."""
    if not model:
        return "other"
    m = model.lower()
    if "deepseek" in m:
        return "deepseek"
    if "xiaomi" in m or "mimo" in m:
        return "mimo"
    return "other"


def _load_records() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("records", [])
    except Exception:
        return []


def _save_records(records: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False)


def record_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs: Any,
) -> None:
    """Registar uso de tokens (chamar a partir do provider/litellm)."""
    if (input_tokens or 0) <= 0 and (output_tokens or 0) <= 0:
        return
    provider = (provider or _derive_provider(model)).lower()
    if provider == "other":
        return  # só agregamos deepseek e mimo para custo
    ts = int(datetime.now(timezone.utc).timestamp())
    record = {
        "ts": ts,
        "provider": provider,
        "model": (model or "")[:64],
        "input_tokens": max(0, input_tokens),
        "output_tokens": max(0, output_tokens),
    }
    with _LOCK:
        records = _load_records()
        records.append(record)
        cutoff = int((datetime.now(timezone.utc) - timedelta(days=_MAX_DAYS_KEPT)).timestamp())
        records = [r for r in records if (r.get("ts") or 0) > cutoff]
        _save_records(records)


def get_usage_summary() -> str | None:
    """Resumo para #ai: uso por provedor, por dia e últimos 7 dias; custo estimado. Sem secrets."""
    with _LOCK:
        records = _load_records()
    if not records:
        return None

    tz = timezone.utc
    now = datetime.now(tz)
    today_start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    week_start = int((now - timedelta(days=7)).timestamp())

    by_day_provider: dict[str, dict[str, dict[str, int]]] = {}
    for r in records:
        ts = r.get("ts") or 0
        if ts < week_start:
            continue
        dt = datetime.fromtimestamp(ts, tz=tz)
        day_key = dt.strftime("%Y-%m-%d")
        prov = (r.get("provider") or "other").lower()
        if prov not in ("deepseek", "mimo"):
            continue
        if day_key not in by_day_provider:
            by_day_provider[day_key] = {}
        if prov not in by_day_provider[day_key]:
            by_day_provider[day_key][prov] = {"input": 0, "output": 0}
        by_day_provider[day_key][prov]["input"] += r.get("input_tokens") or 0
        by_day_provider[day_key][prov]["output"] += r.get("output_tokens") or 0

    today_key = now.strftime("%Y-%m-%d")
    today_stats = by_day_provider.get(today_key, {})
    week_input = {"deepseek": 0, "mimo": 0}
    week_output = {"deepseek": 0, "mimo": 0}
    for day_data in by_day_provider.values():
        for p in ("deepseek", "mimo"):
            week_input[p] += (day_data.get(p) or {}).get("input", 0)
            week_output[p] += (day_data.get(p) or {}).get("output", 0)

    def cost(provider: str, inp: int, out: int) -> float:
        prices = PRICE_PER_1M.get(provider, {})
        return (inp / 1_000_000 * prices.get("input", 0) +
                out / 1_000_000 * prices.get("output", 0))

    lines = []
    for label, inp_d, out_d in [
        ("Hoje", today_stats.get("deepseek", {}).get("input", 0) + today_stats.get("mimo", {}).get("input", 0),
         today_stats.get("deepseek", {}).get("output", 0) + today_stats.get("mimo", {}).get("output", 0)),
        ("Últimos 7 dias", week_input["deepseek"] + week_input["mimo"], week_output["deepseek"] + week_output["mimo"]),
    ]:
        lines.append(f"{label}: input {inp_d:,} | output {out_d:,} tokens")

    cost_today = cost("deepseek",
                      today_stats.get("deepseek", {}).get("input", 0),
                      today_stats.get("deepseek", {}).get("output", 0)) + \
                 cost("mimo",
                      today_stats.get("mimo", {}).get("input", 0),
                      today_stats.get("mimo", {}).get("output", 0))
    cost_week = cost("deepseek", week_input["deepseek"], week_output["deepseek"]) + \
               cost("mimo", week_input["mimo"], week_output["mimo"])

    lines.append("")
    lines.append("Custo estimado (USD):")
    lines.append(f"  Hoje: ${cost_today:.4f}")
    lines.append(f"  7 dias: ${cost_week:.4f}")
    lines.append("")
    lines.append("Por provedor (7 dias):")
    for p in ("deepseek", "mimo"):
        inp, out = week_input[p], week_output[p]
        if inp or out:
            lines.append(f"  {p}: in {inp:,} | out {out:,} → ${cost(p, inp, out):.4f}")

    return "\n".join(lines) if lines else None
