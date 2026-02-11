"""Verificação de frustração/reclamação no histórico via Mimo (a cada 20 mensagens)."""


async def check_frustration_or_complaint(
    messages: list[dict],
    scope_provider,
    scope_model: str,
) -> bool:
    """
    Usa Mimo para analisar as últimas mensagens.
    Retorna True se detectar frustração ou reclamação do cliente.
    """
    if not scope_provider or not scope_model or not messages:
        return False
    conv_text = "\n".join(
        f"{m.get('role', '?')}: {(m.get('content') or '')[:200]}"
        for m in messages[-25:]
    )
    prompt = f"""Analisa esta conversa entre utilizador e assistente.
Há FRUSTRAÇÃO ou RECLAMAÇÃO por parte do utilizador? (ex.: insatisfeito, irritado, queixa sobre o serviço, pedidos repetidos sem resultado, "não funciona", "cadê", "errado", etc.)
Responde APENAS: SIM ou NAO
- SIM = há frustração ou reclamação clara
- NAO = conversa normal, sem sinais de insatisfação

Conversa:
{conv_text[:2000]}"""

    try:
        r = await scope_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=scope_model,
            max_tokens=10,
            temperature=0,
        )
        raw = (r.content or "").strip().upper()
        return "SIM" in raw or raw.startswith("S")
    except Exception:
        return False
