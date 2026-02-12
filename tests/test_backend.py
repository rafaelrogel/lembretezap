"""Tests for backend: scope filter, DB models, API."""

import os
import tempfile

import pytest


def test_scope_filter_in_scope():
    from backend.scope_filter import is_in_scope_fast
    assert is_in_scope_fast("me lembre de beber agua em 2 min") is True
    assert is_in_scope_fast("/list mercado add leite") is True
    assert is_in_scope_fast("/feito 1") is True
    assert is_in_scope_fast("lista de compras: arroz") is True
    assert is_in_scope_fast("/filme Matrix") is True


def test_scope_filter_out_of_scope():
    from backend.scope_filter import is_in_scope_fast
    assert is_in_scope_fast("o que voce acha da politica?") is False
    assert is_in_scope_fast("conta uma piada") is False
    assert is_in_scope_fast("") is False


@pytest.mark.asyncio
async def test_scope_filter_llm_sim_nao():
    from backend.scope_filter import is_in_scope_llm
    from nanobot.providers.base import LLMResponse

    class MockProvider:
        async def chat(self, messages, tools=None, model=None, max_tokens=10, temperature=0.7):
            return LLMResponse(content="SIM", tool_calls=[])
        def get_default_model(self):
            return "test"

    class MockProviderNao:
        async def chat(self, messages, tools=None, model=None, max_tokens=10, temperature=0.7):
            return LLMResponse(content="NAO", tool_calls=[])
        def get_default_model(self):
            return "test"

    assert await is_in_scope_llm("qual o sentido da vida?", MockProvider()) is True
    assert await is_in_scope_llm("qual o sentido da vida?", MockProviderNao()) is False
    from backend.scope_filter import is_in_scope_fast
    assert await is_in_scope_llm("text", None) == is_in_scope_fast("text")


def test_guardrails_should_skip_reply():
    """Não responder a mensagens triviais (ok, tá, emojis); sim/não passam para confirmações."""
    from backend.guardrails import should_skip_reply
    assert should_skip_reply("") is True
    assert should_skip_reply("   ") is True
    assert should_skip_reply("ok") is True
    assert should_skip_reply("OK") is True
    assert should_skip_reply("tá") is True
    assert should_skip_reply("nope") is True
    assert should_skip_reply("ah ok") is True
    assert should_skip_reply("👍") is True
    assert should_skip_reply("😊") is True
    assert should_skip_reply("  ok  ") is True
    # sim/não/yes/no não são triviais: usados em confirmações (lembrete) e devem ser processados
    assert should_skip_reply("sim") is False
    assert should_skip_reply("Sim") is False
    assert should_skip_reply("não") is False
    assert should_skip_reply("nao") is False
    assert should_skip_reply("yes") is False
    assert should_skip_reply("no") is False
    assert should_skip_reply("bom dia") is False
    assert should_skip_reply("lembra-me às 9h") is False
    assert should_skip_reply("não quero") is False


def test_models_and_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models_db import Base, User, List, ListItem, _truncate_phone

    assert _truncate_phone("5511999999999") == "5511***9999"
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        user = User(phone_hash="abc123", phone_truncated="5511***9999")
        db.add(user)
        db.commit()
        db.refresh(user)
        lst = List(user_id=user.id, name="mercado")
        db.add(lst)
        db.commit()
        db.refresh(lst)
        item = ListItem(list_id=lst.id, text="leite")
        db.add(item)
        db.commit()
        assert user.id is not None
        assert lst.name == "mercado"
        assert item.text == "leite"
    finally:
        db.close()
        engine.dispose()
        try:
            os.unlink(path)
        except PermissionError:
            pass


def test_command_parser():
    from backend.command_parser import parse

    # /lembrete pontual
    i = parse("/lembrete beber agua daqui a 2 min")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("in_seconds") == 120 and "beber agua" in i.get("message", "")
    i = parse("/lembrete x em 5 minutos")
    assert i is not None and i.get("in_seconds") == 300

    # /lembrete com barra extra: "daqui a 30 min/ texto" → mensagem sem "/" no início
    i = parse("/lembrete daqui a 30 min/ lembre-me de ir ao RPG")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("in_seconds") == 1800
    assert i.get("message", "").strip() == "lembre-me de ir ao RPG"
    assert not (i.get("message") or "").strip().startswith("/")

    # /lembrete recorrente: diário
    i = parse("/lembrete todo dia às 9h tomar remédio")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("cron_expr") == "0 9 * * *" and "tomar remédio" in i.get("message", "")
    i = parse("/lembrete todos os dias tomar vitamina")
    assert i is not None and i.get("cron_expr") == "0 9 * * *"

    # /lembrete recorrente: semanal
    i = parse("/lembrete toda segunda às 10h reunião")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("cron_expr") == "0 10 * * 1" and "reunião" in i.get("message", "")

    # /lembrete recorrente: a cada N
    i = parse("/lembrete a cada 2 horas beber água")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("every_seconds") == 7200 and "beber água" in i.get("message", "")

    # /lembrete recorrente: mensal
    i = parse("/lembrete mensalmente dia 1 às 9h pagar contas")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("cron_expr") == "0 9 1 * *" and "pagar contas" in i.get("message", "")

    # /lembrete encadeado: depois de X
    i = parse("/lembrete enviar relatório depois de PIX")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("depends_on_job_id") == "PIX" and "enviar relatório" in i.get("message", "")
    i = parse("/lembrete B em 10 min depois de AL")
    assert i is not None and i.get("depends_on_job_id") == "AL" and i.get("in_seconds") == 600

    # /list
    i = parse("/list mercado add leite")
    assert i == {"type": "list_add", "list_name": "mercado", "item": "leite"}
    i = parse("/list pendentes")
    assert i == {"type": "list_show", "list_name": "pendentes"}
    i = parse("/list")
    assert i == {"type": "list_show", "list_name": None}

    # /feito
    i = parse("/feito 1")
    assert i == {"type": "feito", "list_name": None, "item_id": 1}
    i = parse("/feito mercado 2")
    assert i == {"type": "feito", "list_name": "mercado", "item_id": 2}

    # /filme, /livro, /musica, /receita → list_add (tudo dentro de /list)
    i = parse("/filme Matrix")
    assert i == {"type": "list_add", "list_name": "filme", "item": "Matrix"}
    i = parse("/filme O Senhor dos Anéis")
    assert i is not None and i["type"] == "list_add" and i["list_name"] == "filme" and "Senhor" in i["item"]
    i = parse("/list filme Inception")
    assert i == {"type": "list_add", "list_name": "filme", "item": "Inception"}
    i = parse("/list receita Bolo de chocolate")
    assert i is not None and i["type"] == "list_add" and i["list_name"] == "receita"
    i = parse("/receita Torta de maçã")
    assert i == {"type": "list_add", "list_name": "receita", "item": "Torta de maçã"}

    # Não comando
    assert parse("me lembre amanhã") is None
    assert parse("") is None


def test_rate_limit():
    """Token bucket: first max_per_minute allowed, then rate limited."""
    from backend.rate_limit import is_rate_limited, get_remaining, reset_for_test

    reset_for_test("test:")

    # First 15 (default max) should be allowed
    for _ in range(15):
        assert is_rate_limited("test", "user_xyz_123") is False
    # 16th should be limited
    assert is_rate_limited("test", "user_xyz_123") is True
    assert get_remaining("test", "user_xyz_123") == 0


def test_rate_limit_token_bucket_refill():
    """Token bucket refills over time; after refill one more request is allowed."""
    import time
    from backend.rate_limit import is_rate_limited, get_remaining, reset_for_test

    reset_for_test("test_refill:")

    # Exhaust bucket: 2 tokens, refill 2/6 per sec (so in 3s we get 1 token)
    assert is_rate_limited("test_refill", "u1", max_per_minute=2, window_seconds=6) is False
    assert is_rate_limited("test_refill", "u1", max_per_minute=2, window_seconds=6) is False
    assert is_rate_limited("test_refill", "u1", max_per_minute=2, window_seconds=6) is True

    # After 3s we have ~1 token refilled
    time.sleep(3.5)
    assert get_remaining("test_refill", "u1", max_per_minute=2, window_seconds=6) >= 1
    assert is_rate_limited("test_refill", "u1", max_per_minute=2, window_seconds=6) is False


def test_command_filter():
    """Blocklist: shell, SQL, path patterns bloqueados; mensagens normais permitidas."""
    from backend.command_filter import is_blocked
    assert is_blocked("rm -rf /") == (True, "rm_rf_root")
    assert is_blocked("DROP TABLE users") == (True, "sql_drop")
    assert is_blocked("lembrete beber agua") == (False, "")
    assert is_blocked("lista mercado add leite") == (False, "")


def test_fastapi_health():
    from fastapi.testclient import TestClient
    from backend.app import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_fastapi_api_key_auth():
    """Com API_SECRET_KEY definido, /users exige X-API-Key; sem key ou errada = 401/403."""
    import backend.auth as auth_module
    from fastapi.testclient import TestClient
    from backend.app import app

    client = TestClient(app)
    original = auth_module.API_SECRET_KEY
    try:
        auth_module.API_SECRET_KEY = "test-secret"
        r_no_header = client.get("/users")
        assert r_no_header.status_code in (401, 403)
        r_wrong = client.get("/users", headers={"X-API-Key": "wrong"})
        assert r_wrong.status_code in (401, 403)
        r_ok = client.get("/users", headers={"X-API-Key": "test-secret"})
        assert r_ok.status_code == 200
    finally:
        auth_module.API_SECRET_KEY = original


def test_config_get_provider_fallback_when_matched_provider_has_no_key():
    """When model matches a provider (e.g. anthropic) but that provider has no api_key, fallback to first with key."""
    from nanobot.config.schema import Config, ProviderConfig, ProvidersConfig, AgentsConfig, AgentDefaults

    # Only openrouter has key; model is anthropic
    providers = ProvidersConfig(
        anthropic=ProviderConfig(api_key=""),
        openrouter=ProviderConfig(api_key="sk-or-secret"),
    )
    agents = AgentsConfig(defaults=AgentDefaults(model="anthropic/claude-3.5-sonnet"))
    config = Config(agents=agents, providers=providers)

    p = config.get_provider()
    assert p is not None
    assert p.api_key == "sk-or-secret"
    assert p == config.providers.openrouter
