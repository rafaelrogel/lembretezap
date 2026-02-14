"""
Classificação de intenção (NLU) para o assistente.

Usa prompt estruturado + LLM para retornar IntentClassification,
que alimenta o roteamento para tools (cron, list_tool, etc.).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Callable, Awaitable

from zapista.config.domain_ontology import (
    ExtractedEntity,
    FollowUpSuggestion,
    IntentClassification,
    TaskType,
    EntityType,
)

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "intent_classification.txt"


def _load_prompt() -> str:
    """Carrega o prompt de classificação."""
    path = _PROMPT_PATH
    if not path.exists():
        raise FileNotFoundError(f"Prompt não encontrado: {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> str:
    """Extrai JSON do texto, removendo blocos markdown ou texto antes/depois."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    # Fallback: primeiro { até último }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


async def classify_intent(
    user_message: str,
    llm_complete: Callable[[str, int, float], Awaitable[str]],
    *,
    max_tokens: int = 500,
    temperature: float = 0.1,
) -> IntentClassification:
    """
    Classifica a intenção da mensagem usando LLM com prompt estruturado.

    Args:
        user_message: Mensagem do usuário.
        llm_complete: Função async que recebe (prompt, max_tokens, temperature) e retorna texto.
        max_tokens: Tokens máximos na resposta.
        temperature: Temperatura para geração (baixa = mais determinístico).

    Returns:
        IntentClassification com task_type, entities, etc.

    Raises:
        FileNotFoundError: Se o prompt não existir.
    """
    template = _load_prompt()
    prompt = template.replace("{user_message}", user_message)
    response = await llm_complete(prompt, max_tokens, temperature)

    try:
        raw = _extract_json(response)
        data = json.loads(raw)

        # Remove campos que não vão no Pydantic
        data.pop("raw_text", None)
        if "entities" in data:
            data["entities"] = [
                ExtractedEntity(
                    type=EntityType(e["type"]),
                    value=str(e["value"]),
                    confidence=float(e.get("confidence", 0.9)),
                )
                for e in data["entities"]
            ]
        if data.get("follow_up_suggestion"):
            fs = data["follow_up_suggestion"]
            data["follow_up_suggestion"] = FollowUpSuggestion(
                task_type=TaskType(fs["task_type"]),
                entities=[
                    ExtractedEntity(
                        type=EntityType(e["type"]),
                        value=str(e["value"]),
                        confidence=float(e.get("confidence", 0.9)),
                    )
                    for e in fs.get("entities", [])
                ],
                prompt_text=fs.get("prompt_text"),
            )

        intent = IntentClassification(**data, raw_text=user_message)
        logger.info("Intent classified: %s (conf=%.2f)", intent.task_type.value, intent.confidence)
        return intent

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.error("Failed to parse intent: %s | raw: %r", e, response[:200])
        return IntentClassification(
            task_type=TaskType.GENERAL,
            confidence=0.5,
            entities=[],
            raw_text=user_message,
            requires_clarification=True,
        )
