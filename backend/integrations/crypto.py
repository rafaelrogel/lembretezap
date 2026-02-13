"""Criptomoedas — cotação atual via CoinGecko (API gratuita)."""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.handler_context import HandlerContext


def is_crypto_intent(content: str) -> bool:
    """Detecta se o utilizador pergunta sobre criptomoedas."""
    t = (content or "").strip().lower()
    if not t or len(t) < 4:
        return False
    patterns = [
        r"bitcoin|btc\b",
        r"ethereum|eth\b",
        r"tether|usdt\b",
        r"xrp\b",
        r"bnb\b",
        r"cripto(?:moeda|s)?",
        r"cota[cç][aã]o\s+(?:de\s+)?(?:cripto|bitcoin|eth)",
        r"pre[cç]o\s+(?:do\s+)?(?:bitcoin|eth|cripto)",
        r"quanto\s+(?:est[aá]|vale)\s+(?:o\s+)?(?:bitcoin|eth)",
        r"valor\s+(?:do\s+)?(?:bitcoin|eth|cripto)",
    ]
    return any(re.search(p, t) for p in patterns)


async def handle_crypto(ctx: "HandlerContext", content: str) -> str | None:
    """Quando o utilizador fala de cripto, responde com cotação atual (BTC, ETH, USDT, XRP, BNB)."""
    if not is_crypto_intent(content):
        return None
    from backend.crypto_prices import fetch_crypto_prices, build_crypto_message
    data = fetch_crypto_prices()
    return build_crypto_message(data)
