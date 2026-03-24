"""Autenticação da API: API key opcional via header X-API-Key.

Se API_SECRET_KEY não estiver definido, os endpoints protegidos ficam acessíveis (desenvolvimento).
Em produção definir API_SECRET_KEY e enviar header X-API-Key em todas as requisições à API.
"""

import os
import hmac
from typing import Annotated

from fastapi import Header, HTTPException

API_SECRET_KEY = os.environ.get("API_SECRET_KEY", "").strip() or None


def verify_api_key(provided_key: str, expected_key: str) -> bool:
    return hmac.compare_digest(
        provided_key.encode("utf-8"),
        expected_key.encode("utf-8")
    )


def require_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    """Dependency: exige X-API-Key igual a API_SECRET_KEY quando este está definido."""
    if API_SECRET_KEY is None:
        return
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")
    if not verify_api_key(x_api_key.strip(), API_SECRET_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")
