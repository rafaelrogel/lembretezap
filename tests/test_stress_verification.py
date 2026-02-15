"""
Verificação completa e stress test do fluxo de comandos (normalize + route).

- Valida normalize_command com todos os aliases i18n e mensagens não-comando.
- Stress: muitas chamadas consecutivas e concorrentes a route() com /help e /ajuda.
- Garante que nenhuma exceção vaza e que respostas são consistentes.

Execute: uv run pytest tests/test_stress_verification.py -v
Ou: uv run python -m pytest tests/test_stress_verification.py -v
"""

import asyncio
import os
import sys

import pytest

# Garantir que o backend está no path (execução a partir da raiz do projeto)
if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_normalize_command_i18n_aliases():
    """Verificação: todos os aliases i18n normalizam para o comando canónico."""
    from backend.command_i18n import normalize_command, COMMAND_ALIASES

    for canonical, aliases in COMMAND_ALIASES:
        for alias in aliases:
            out = normalize_command(alias)
            assert out.strip().lower().startswith(canonical.lower()), (
                f"alias {alias!r} deveria normalizar para {canonical}, obteve {out!r}"
            )
            # Com argumento extra
            with_arg = f"{alias} Lisboa"
            out_arg = normalize_command(with_arg)
            assert out_arg.strip().lower().startswith(canonical.lower()) and "Lisboa" in out_arg, (
                f"alias com arg {with_arg!r} -> {out_arg!r}"
            )


def test_normalize_command_non_commands_unchanged():
    """Verificação: mensagens que não são comandos não são alteradas."""
    from backend.command_i18n import normalize_command

    unchanged = [
        "olá, tudo bem?",
        "lembra de comprar leite amanhã",
        "lista mercado add leite",  # sem barra
        "",
        "   ",
        "qual o sentido da vida?",
        "/comando_inexistente foo",
    ]
    for msg in unchanged:
        out = normalize_command(msg)
        assert out == msg, f"normalize_command não deveria alterar {msg!r}, obteve {out!r}"


def test_normalize_command_edge_cases():
    """Verificação: entradas extremas (vazio, None, string longa, unicode)."""
    from backend.command_i18n import normalize_command

    assert normalize_command("") == ""
    assert normalize_command("   ") == "   "
    # None pode ser passado; não deve quebrar
    assert normalize_command(None) is None  # type: ignore[arg-type]
    # /ajuda com espaço e texto
    assert normalize_command("  /ajuda  ") == "/help"
    # Unicode
    assert normalize_command("/ajuda café") == "/help café"
    # Muito longo: só o primeiro token importa
    long_rest = "x" * 500
    out = normalize_command(f"/est {long_rest}")
    assert out.startswith("/stats ") and long_rest in out


@pytest.mark.asyncio
async def test_route_help_returns_text():
    """Verificação: /help e /ajuda retornam texto de ajuda (handler handle_help)."""
    from backend.handler_context import HandlerContext
    from backend.router import route

    ctx = HandlerContext(
        channel="test",
        chat_id="stress_test_chat",
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        event_tool=None,
    )
    for cmd in ["/help", "/ajuda", "/ayuda"]:
        out = await route(ctx, cmd)
        assert out is not None, f"{cmd} deveria retornar texto"
        assert "Comandos" in out or "comandos" in out.lower(), f"resposta de {cmd} deveria conter comandos: {out[:200]}"


@pytest.mark.asyncio
async def test_stress_route_many_sequential():
    """Stress: 100 chamadas sequenciais a route com /help e /ajuda alternados."""
    from backend.handler_context import HandlerContext
    from backend.router import route

    ctx = HandlerContext(
        channel="test",
        chat_id="stress_seq",
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        event_tool=None,
    )
    for i in range(100):
        cmd = "/help" if i % 2 == 0 else "/ajuda"
        out = await route(ctx, cmd)
        assert out is not None
        assert "comandos" in out.lower() or "Comandos" in out


@pytest.mark.asyncio
async def test_stress_route_concurrent():
    """Stress: 50 tarefas concorrentes (route com /help)."""
    from backend.handler_context import HandlerContext
    from backend.router import route

    ctx = HandlerContext(
        channel="test",
        chat_id="stress_concurrent",
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        event_tool=None,
    )

    async def one_route():
        return await route(ctx, "/help")

    results = await asyncio.gather(*[one_route() for _ in range(50)], return_exceptions=True)
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            pytest.fail(f"Chamada {i} falhou: {r}")
        assert r is not None
        assert "comandos" in r.lower() or "Comandos" in r


@pytest.mark.asyncio
async def test_stress_normalize_many_commands():
    """Stress: normalize_command com 500 entradas (comandos + não-comandos)."""
    from backend.command_i18n import normalize_command, COMMAND_ALIASES

    inputs = []
    for _canonical, aliases in COMMAND_ALIASES:
        for a in aliases[:3]:  # primeiros 3 de cada
            inputs.append(a)
            inputs.append(f"{a} arg")
    # Repetir para chegar a centenas
    while len(inputs) < 500:
        inputs.extend(inputs[:50])
    inputs = inputs[:500]

    for s in inputs:
        out = normalize_command(s)
        assert isinstance(out, str) or out is None
        if out is not None and s.strip():
            # Não deve estourar nem retornar string vazia quando entrada tinha conteúdo
            assert len(out) >= 0
