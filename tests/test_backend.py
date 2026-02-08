"""Tests for backend: scope filter, DB models, API."""

import pytest
from pathlib import Path
import tempfile
import os

# Force backend on path when running tests from repo root
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


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

    # /lembrete
    i = parse("/lembrete beber agua daqui a 2 min")
    assert i is not None and i["type"] == "lembrete"
    assert i.get("in_seconds") == 120 and "beber agua" in i.get("message", "")
    i = parse("/lembrete x em 5 minutos")
    assert i is not None and i.get("in_seconds") == 300

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

    # /filme
    i = parse("/filme Matrix")
    assert i == {"type": "filme", "nome": "Matrix"}
    i = parse("/filme O Senhor dos Anéis")
    assert i is not None and i["type"] == "filme" and "Senhor" in i["nome"]

    # Não comando
    assert parse("me lembre amanhã") is None
    assert parse("") is None


def test_rate_limit():
    from backend.rate_limit import is_rate_limited, get_remaining

    # Reset state by using a unique key
    import backend.rate_limit as rl
    key = "test:user_xyz_123"
    with rl._lock:
        rl._entries[key] = []

    # First 15 (default max) should be allowed
    for _ in range(15):
        assert is_rate_limited("test", "user_xyz_123") is False
    # 16th should be limited
    assert is_rate_limited("test", "user_xyz_123") is True
    assert get_remaining("test", "user_xyz_123") == 0


def test_fastapi_health():
    from fastapi.testclient import TestClient
    from backend.app import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
