"""
Testes unitários para classificação de intenção (NLU).

Usa mock do LLM para evitar chamadas reais — testes rápidos e determinísticos.
Para testes contra LLM real, use @pytest.mark.integration e rode com -m integration.
"""

import json
import pytest

from zapista.config.domain_ontology import (
    EntityType,
    ExtractedEntity,
    FollowUpSuggestion,
    IntentClassification,
    TaskType,
)
from zapista.agent.nlu import classify_intent, _extract_json


# --- Mock LLM ---


def _mock_llm(response: str):
    """Retorna uma função async que sempre devolve a mesma resposta."""

    async def _complete(_prompt: str, _max_tokens: int, _temperature: float) -> str:
        return response

    return _complete


# --- Testes de parse/extract ---


def test_extract_json_plain():
    """JSON puro retorna igual."""
    assert _extract_json('{"task_type": "reminder"}') == '{"task_type": "reminder"}'


def test_extract_json_markdown_block():
    """Remove bloco ```json ... ```."""
    raw = 'Aqui está:\n```json\n{"task_type": "list"}\n```'
    assert _extract_json(raw) == '{"task_type": "list"}'


def test_extract_json_text_before_and_after():
    """Extrai JSON entre { e } quando há texto ao redor."""
    raw = 'Sure! Here is the result: {"task_type": "query", "confidence": 0.9} Hope that helps.'
    result = _extract_json(raw)
    assert "task_type" in result and "query" in result


# --- Testes de classificação com mock ---


@pytest.mark.asyncio
async def test_classify_reminder():
    """Lembrete com datetime e item_name."""
    response = json.dumps({
        "task_type": "reminder",
        "confidence": 0.95,
        "entities": [
            {"type": "item_name", "value": "ligar pro médico", "confidence": 0.9},
            {"type": "datetime", "value": "amanhã 14h", "confidence": 0.95},
        ],
        "requires_clarification": False,
        "clarification_options": None,
        "follow_up_suggestion": None,
    })
    llm = _mock_llm(response)
    intent = await classify_intent("me lembra de ligar pro médico amanhã 14h", llm)

    assert intent.task_type == TaskType.REMINDER
    assert intent.confidence > 0.8
    assert intent.raw_text == "me lembra de ligar pro médico amanhã 14h"
    assert any(e.type == EntityType.DATETIME for e in intent.entities)
    assert any(e.type == EntityType.ITEM_NAME for e in intent.entities)


@pytest.mark.asyncio
async def test_classify_list_with_media():
    """Lista com media_title e category."""
    response = json.dumps({
        "task_type": "list",
        "confidence": 0.9,
        "entities": [
            {"type": "media_title", "value": "Interestelar", "confidence": 0.95},
            {"type": "category", "value": "filmes", "confidence": 0.9},
        ],
        "requires_clarification": False,
        "clarification_options": None,
        "follow_up_suggestion": None,
    })
    llm = _mock_llm(response)
    intent = await classify_intent("adiciona Interestelar na lista de filmes", llm)

    assert intent.task_type == TaskType.LIST
    assert any(e.type == EntityType.MEDIA_TITLE for e in intent.entities)
    assert any(e.type == EntityType.CATEGORY for e in intent.entities)


@pytest.mark.asyncio
async def test_classify_recurring_task():
    """Tarefa recorrente com recurrence."""
    response = json.dumps({
        "task_type": "recurring",
        "confidence": 0.95,
        "entities": [
            {"type": "recurrence", "value": "toda sexta às 17h", "confidence": 0.95},
            {"type": "item_name", "value": "sair mais cedo", "confidence": 0.9},
        ],
        "requires_clarification": False,
        "clarification_options": None,
        "follow_up_suggestion": None,
    })
    llm = _mock_llm(response)
    intent = await classify_intent("me lembra toda sexta às 17h de sair mais cedo", llm)

    assert intent.task_type == TaskType.RECURRING_TASK
    assert any(e.type == EntityType.RECURRENCE for e in intent.entities)


@pytest.mark.asyncio
async def test_classify_with_follow_up_suggestion():
    """Lembrete com follow_up_suggestion (itens para lista)."""
    response = json.dumps({
        "task_type": "reminder",
        "confidence": 0.95,
        "entities": [
            {"type": "datetime", "value": "14/02 11h", "confidence": 0.95},
            {"type": "item_name", "value": "ir ao mercadinho", "confidence": 0.9},
        ],
        "requires_clarification": False,
        "clarification_options": None,
        "follow_up_suggestion": {
            "task_type": "list",
            "entities": [
                {"type": "item_name", "value": "carne do sol", "confidence": 0.95},
                {"type": "item_name", "value": "farinha de mandioca", "confidence": 0.95},
            ],
            "prompt_text": "Quer que eu adicione carne do sol e farinha de mandioca na lista de compras?",
        },
    })
    llm = _mock_llm(response)
    intent = await classify_intent(
        "Hoje 14/02 preciso ser lembrado de ir ao mercadinho às 11h para comprar carne do sol e farinha",
        llm,
    )

    assert intent.task_type == TaskType.REMINDER
    assert intent.follow_up_suggestion is not None
    assert intent.follow_up_suggestion.task_type == TaskType.LIST
    assert len(intent.follow_up_suggestion.entities) == 2
    assert "carne do sol" in intent.follow_up_suggestion.prompt_text


@pytest.mark.asyncio
async def test_classify_fallback_on_parse_error():
    """Fallback GENERAL quando JSON inválido."""
    llm = _mock_llm("This is not JSON at all")
    intent = await classify_intent("alguma mensagem", llm)

    assert intent.task_type == TaskType.GENERAL
    assert intent.confidence == 0.5
    assert intent.requires_clarification is True
    assert intent.raw_text == "alguma mensagem"


# --- Testes de domain_ontology ---


def test_intent_derive_clarification_from_low_confidence():
    """Confidence < 0.7 força requires_clarification=True."""
    intent = IntentClassification(
        task_type=TaskType.REMINDER,
        confidence=0.6,
        entities=[],
        raw_text="teste",
    )
    assert intent.requires_clarification is True


def test_intent_no_clarification_when_high_confidence():
    """Confidence >= 0.7 mantém requires_clarification=False."""
    intent = IntentClassification(
        task_type=TaskType.REMINDER,
        confidence=0.9,
        entities=[],
        raw_text="teste",
    )
    assert intent.requires_clarification is False
