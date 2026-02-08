"""Teste de carga: 100 clientes simultâneos contra a API."""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_100_concurrent_clients_health():
    """100 requisições simultâneas a GET /health; todas devem retornar 200."""
    import httpx
    from httpx import ASGITransport, AsyncClient

    from backend.app import app

    transport = ASGITransport(app=app)
    num_clients = 100
    base_url = "http://testserver"

    async with AsyncClient(transport=transport, base_url=base_url, timeout=10.0) as client:
        tasks = [client.get("/health") for _ in range(num_clients)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in responses if isinstance(r, Exception)]
    assert not errors, f"Erros nas requisições: {errors[:5]}{'...' if len(errors) > 5 else ''}"

    ok = [r for r in responses if not isinstance(r, Exception) and r.status_code == 200]
    assert len(ok) == num_clients, (
        f"Esperado {num_clients} respostas 200, obtidas {len(ok)}. "
        f"Outras: {[r.status_code for r in responses if not isinstance(r, Exception) and r.status_code != 200][:10]}"
    )
    for r in ok:
        assert r.json() == {"status": "ok"}
