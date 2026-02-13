"""Cotação de criptomoedas via CoinGecko API (gratuita, sem API key)."""

import urllib.request
import json
from typing import Any

COINGECKO_IDS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "tether": "USDT",
    "ripple": "XRP",   # XRP na CoinGecko = ripple
    "binancecoin": "BNB",
}

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/simple/price"
    "?ids=bitcoin,ethereum,tether,ripple,binancecoin"
    "&vs_currencies=usd,eur"
)


def fetch_crypto_prices() -> dict[str, dict[str, float]] | None:
    """
    Obtém cotação atual de BTC, ETH, USDT, XRP, BNB.
    Retorna {id: {usd: float, eur: float}} ou None se falhar.
    """
    try:
        req = urllib.request.Request(
            COINGECKO_URL,
            headers={"Accept": "application/json", "User-Agent": "zapista/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def build_crypto_message(data: dict[str, dict[str, float]] | None) -> str:
    """Constrói mensagem com cotações em USD e EUR."""
    if not data:
        return "Não foi possível obter as cotações agora. Tenta mais tarde."

    def _fmt(v: float) -> str:
        if v >= 1000:
            return f"{v:,.0f}"
        if v >= 1:
            return f"{v:,.2f}"
        return f"{v:.4f}"

    lines = ["📊 **Cotação de criptomoedas**\n"]
    for cg_id, symbol in COINGECKO_IDS.items():
        if cg_id not in data:
            continue
        d = data[cg_id]
        usd = d.get("usd") or 0
        eur = d.get("eur") or 0
        lines.append(f"• **{symbol}** — ${_fmt(usd)} | €{_fmt(eur)}")
    return "\n".join(lines)
