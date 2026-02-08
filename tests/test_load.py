"""Testes de carga e stress: múltiplos clientes e utilizadores simulados."""

import asyncio
import time
import pytest

# API key usada no stress test com endpoints de dados (BD temporária)
_STRESS_API_KEY = "stress-test-api-key"


def _get_app_client():
    """Cliente HTTP async contra a app FastAPI (in-process)."""
    import httpx
    from httpx import ASGITransport, AsyncClient
    from backend.app import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver", timeout=15.0)


def _make_stress_app_with_temp_db():
    """
    Cria BD em ficheiro temporário com utilizadores/listas/eventos de teste e override de get_db.
    Ficheiro permite múltiplas conexões concorrentes (em memória com uma conexão falhava com 8 users).
    Retorna (app, headers com X-API-Key, cleanup).
    """
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import NullPool

    from backend.app import app
    from backend.database import get_db
    from backend.models_db import Base, User, List, ListItem, Event, AuditLog
    import backend.auth as auth_module

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    # NullPool: cada request usa a sua própria conexão (evita InterfaceError com concorrência)
    engine = create_engine(
        f"sqlite:///{tmp.name}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionTemp = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionTemp()
        try:
            yield db
        finally:
            db.close()

    # Dados de teste: 3 users, listas e eventos (campos obrigatórios explícitos para evitar None)
    db = SessionTemp()
    try:
        for i in range(1, 4):
            u = User(phone_hash=f"stress_hash_{i}", phone_truncated=f"551***{i}")
            db.add(u)
        db.flush()
        for i in range(1, 4):
            db.add(List(user_id=i, name="mercado"))
            db.add(List(user_id=i, name="pendentes"))
        db.flush()
        for lst in db.query(List).all()[:2]:
            db.add(ListItem(list_id=lst.id, text="leite", done=False))
        db.flush()
        for i in range(1, 4):
            db.add(Event(user_id=i, tipo="filme", payload={"nome": "Matrix"}, deleted=False))
        db.add(AuditLog(user_id=1, action="list_add", resource="mercado"))
        db.commit()
    finally:
        db.close()

    app.dependency_overrides[get_db] = override_get_db
    old_api_key = auth_module.API_SECRET_KEY
    auth_module.API_SECRET_KEY = _STRESS_API_KEY
    headers = {"X-API-Key": _STRESS_API_KEY}

    def cleanup():
        app.dependency_overrides.pop(get_db, None)
        auth_module.API_SECRET_KEY = old_api_key
        try:
            import os
            os.unlink(tmp.name)
        except Exception:
            pass

    return app, headers, cleanup


@pytest.mark.asyncio
async def test_100_concurrent_clients_health():
    """100 requisições simultâneas a GET /health; todas devem retornar 200."""
    num_clients = 100
    async with _get_app_client() as client:
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


@pytest.mark.asyncio
async def test_stress_8_users():
    """
    Stress test: 8 utilizadores concorrentes; cada um faz várias requisições à API.
    Cada 'user' é uma task que executa N pedidos (health). Verifica que todos passam e regista duração.
    """
    num_users = 8
    requests_per_user = 25  # 8 * 25 = 200 requisições no total
    start = time.perf_counter()
    results: list[list[int]] = []  # por user: lista de status codes

    async def one_user(user_id: int) -> list[int]:
        statuses: list[int] = []
        async with _get_app_client() as client:
            for _ in range(requests_per_user):
                r = await client.get("/health")
                statuses.append(r.status_code)
        return statuses

    tasks = [one_user(i) for i in range(num_users)]
    user_results = await asyncio.gather(*tasks, return_exceptions=True)
    elapsed = time.perf_counter() - start

    errors = [u for u in user_results if isinstance(u, Exception)]
    assert not errors, f"Erros em utilizadores: {errors[:3]}"

    for res in user_results:
        if isinstance(res, list):
            results.append(res)
        else:
            results.append([])

    total_requests = sum(len(r) for r in results)
    all_ok = all(sc == 200 for r in results for sc in r)
    assert total_requests == num_users * requests_per_user, f"Esperado {num_users * requests_per_user} requests, obtidos {total_requests}"
    assert all_ok, f"Algumas requisições não foram 200: {[sc for r in results for sc in r if sc != 200][:20]}"

    # Log para análise (visível com pytest -v ou -s)
    req_per_sec = total_requests / elapsed if elapsed > 0 else 0
    print(f"\n[stress] {num_users} users x {requests_per_user} req = {total_requests} requests em {elapsed:.2f}s (~{req_per_sec:.0f} req/s)")


@pytest.mark.asyncio
async def test_stress_6_users():
    """Stress test com 6 utilizadores (variante do de 8)."""
    num_users = 6
    requests_per_user = 30  # 180 total
    start = time.perf_counter()
    results: list[list[int]] = []

    async def one_user(_: int) -> list[int]:
        statuses: list[int] = []
        async with _get_app_client() as client:
            for _ in range(requests_per_user):
                r = await client.get("/health")
                statuses.append(r.status_code)
        return statuses

    user_results = await asyncio.gather(*[one_user(i) for i in range(num_users)], return_exceptions=True)
    elapsed = time.perf_counter() - start

    for res in user_results:
        results.append(res if isinstance(res, list) else [])

    total = sum(len(r) for r in results)
    assert total == num_users * requests_per_user
    assert all(sc == 200 for r in results for sc in r)
    print(f"\n[stress] {num_users} users x {requests_per_user} req = {total} requests em {elapsed:.2f}s (~{total / elapsed:.0f} req/s)")


@pytest.mark.asyncio
async def test_stress_8_users_full_backend():
    """
    Stress test com 8 utilizadores contra o backend completo:
    BD temporária (3 users, listas, eventos) + API key. Cada user faz health + /users + /users/{id}/lists + /users/{id}/events.
    """
    import httpx
    from httpx import ASGITransport, AsyncClient

    app, api_headers, cleanup = _make_stress_app_with_temp_db()
    try:
        num_users = 8
        rounds_per_user = 4  # cada user: 4 rondas de 5 pedidos = 20 pedidos
        # Por ronda: health, /users, /users/1/lists, /users/2/lists, /users/1/events
        urls_with_headers: list[tuple[str, dict]] = [
            ("/health", {}),
            ("/users", api_headers),
            ("/users/1/lists", api_headers),
            ("/users/2/lists", api_headers),
            ("/users/1/events", api_headers),
        ]
        start = time.perf_counter()
        results: list[list[int]] = []

        async def one_user(_: int) -> list[int]:
            statuses: list[int] = []
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
                timeout=15.0,
            ) as client:
                for _ in range(rounds_per_user):
                    for url, h in urls_with_headers:
                        r = await client.get(url, headers=h)
                        statuses.append(r.status_code)
            return statuses

        user_results = await asyncio.gather(
            *[one_user(i) for i in range(num_users)],
            return_exceptions=True,
        )
        elapsed = time.perf_counter() - start

        for res in user_results:
            results.append(res if isinstance(res, list) else [])
        total = sum(len(r) for r in results)
        expected = num_users * rounds_per_user * len(urls_with_headers)
        assert total == expected, f"Esperado {expected} requests, obtidos {total}"
        failures = [sc for r in results for sc in r if sc != 200]
        assert not failures, f"Requisições não-200: {failures[:15]}"

        req_per_sec = total / elapsed if elapsed > 0 else 0
        print(
            f"\n[stress full] {num_users} users x {rounds_per_user} rounds x {len(urls_with_headers)} req/round "
            f"= {total} requests em {elapsed:.2f}s (~{req_per_sec:.0f} req/s)"
        )
    finally:
        cleanup()


@pytest.mark.asyncio
async def test_stress_6_users_full_backend():
    """Stress test com 6 utilizadores contra o backend completo (BD temp + /users, /lists, /events)."""
    import httpx
    from httpx import ASGITransport, AsyncClient

    app, api_headers, cleanup = _make_stress_app_with_temp_db()
    try:
        num_users = 6
        rounds_per_user = 5
        urls_with_headers: list[tuple[str, dict]] = [
            ("/health", {}),
            ("/users", api_headers),
            ("/users/1/lists", api_headers),
            ("/users/2/events", api_headers),
        ]
        start = time.perf_counter()
        results: list[list[int]] = []

        async def one_user(_: int) -> list[int]:
            statuses: list[int] = []
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
                timeout=15.0,
            ) as client:
                for _ in range(rounds_per_user):
                    for url, h in urls_with_headers:
                        r = await client.get(url, headers=h)
                        statuses.append(r.status_code)
            return statuses

        user_results = await asyncio.gather(
            *[one_user(i) for i in range(num_users)],
            return_exceptions=True,
        )
        elapsed = time.perf_counter() - start

        for res in user_results:
            results.append(res if isinstance(res, list) else [])

        total = sum(len(r) for r in results)
        expected = num_users * rounds_per_user * len(urls_with_headers)
        assert total == expected
        assert all(sc == 200 for r in results for sc in r)
        print(
            f"\n[stress full] {num_users} users x {rounds_per_user} rounds x {len(urls_with_headers)} req/round "
            f"= {total} requests em {elapsed:.2f}s (~{total / elapsed:.0f} req/s)"
        )
    finally:
        cleanup()
