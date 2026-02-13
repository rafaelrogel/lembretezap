"""Integrações opcionais: crypto, livros sagrados, atendimento."""

from backend.integrations.atendimento import handle_atendimento_request
from backend.integrations.crypto import handle_crypto, is_crypto_intent
from backend.integrations.sacred_text import handle_sacred_text

__all__ = ["handle_atendimento_request", "handle_crypto", "handle_sacred_text", "is_crypto_intent"]
