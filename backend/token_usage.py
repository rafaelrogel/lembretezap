"""Métricas de uso de tokens por provedor (DeepSeek, Mimo). Para #ai admin.

Registo pode ser feito via callback após cada chamada LLM; este módulo expõe
get_usage_summary() para o comando #ai. Por agora retorna placeholder.
"""

from typing import Any


def record_usage(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    **kwargs: Any,
) -> None:
    """Registar uso de tokens (chamar a partir do provider/litellm)."""
    # TODO: persistir em memória ou ficheiro por dia/7d
    pass


def get_usage_summary() -> str | None:
    """Resumo para #ai: uso por dia/7d, input/output, custo estimado. Nunca incluir secrets."""
    # TODO: agregar por provedor (deepseek-chat, xiaomi/mimo), por dia e 7d
    return None
