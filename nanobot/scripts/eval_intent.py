#!/usr/bin/env python3
"""
Script de avaliação da classificação de intenção (NLU).

Usa prompts/task_type_examples.json para medir acurácia do classificador.

Modos:
  --mock      Usa mock que retorna a resposta correta (valida pipeline, 100% esperado)
  (padrão)    Usa LLM real. Requer OPENAI_API_KEY ou passar --llm openai|anthropic

Exemplo:
  uv run python scripts/eval_intent.py --mock
  uv run python scripts/eval_intent.py
  OPENAI_API_KEY=xxx uv run python scripts/eval_intent.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Adiciona raiz do projeto ao path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from zapista.agent.nlu import classify_intent
from zapista.config.domain_ontology import TaskType

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)


def _load_dataset() -> list[tuple[str, str]]:
    """Retorna [(texto, expected_task_type), ...]."""
    path = _root / "prompts" / "task_type_examples.json"
    if not path.exists():
        raise FileNotFoundError(f"Dataset não encontrado: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    examples = []
    for task_type, texts in data.items():
        for text in texts:
            examples.append((text.strip(), task_type))
    return examples


def _build_mock_response(expected_task_type: str) -> str:
    """Constrói JSON que o mock retornará (resposta 'correta')."""
    return json.dumps({
        "task_type": expected_task_type,
        "confidence": 0.95,
        "entities": [],
        "requires_clarification": False,
        "clarification_options": None,
        "follow_up_suggestion": None,
    })


def _make_mock_llm(expected_task_type: str):
    """Retorna função async que retorna a resposta correta para o exemplo."""

    async def _complete(_p: str, _mt: int, _t: float) -> str:
        return _build_mock_response(expected_task_type)

    return _complete


async def _make_openai_llm():
    """Cria LLM usando OpenAI se OPENAI_API_KEY estiver definida."""

    async def _complete(prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise RuntimeError("openai não instalado. Use: pip install openai")
        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",  # ou gpt-4o para melhor precisão
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    return _complete


async def _make_anthropic_llm():
    """Cria LLM usando Anthropic se ANTHROPIC_API_KEY estiver definida."""

    async def _complete(prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise RuntimeError("anthropic não instalado. Use: pip install anthropic")
        client = AsyncAnthropic()
        resp = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
        return text

    return _complete


async def run_eval(mock: bool, llm_provider: str | None) -> None:
    examples = _load_dataset()
    results = []

    if mock:
        for text, expected in examples:
            llm = _make_mock_llm(expected)
            intent = await classify_intent(text, llm)
            results.append((text, expected, intent.task_type.value))
    else:
        if llm_provider == "openai" or (not llm_provider and os.environ.get("OPENAI_API_KEY")):
            llm = await _make_openai_llm()
        elif llm_provider == "anthropic" or (not llm_provider and os.environ.get("ANTHROPIC_API_KEY")):
            llm = await _make_anthropic_llm()
        else:
            print(
                "Configure OPENAI_API_KEY ou ANTHROPIC_API_KEY, ou use --llm openai|anthropic\n"
                "Exemplo: OPENAI_API_KEY=sk-xxx uv run python scripts/eval_intent.py"
            )
            sys.exit(1)

        for i, (text, expected) in enumerate(examples):
            intent = await classify_intent(text, llm)
            results.append((text, expected, intent.task_type.value))
            if (i + 1) % 10 == 0:
                print(f"  Processados {i + 1}/{len(examples)}...", flush=True)

    # Relatório
    correct = sum(1 for _, exp, got in results if exp == got)
    total = len(results)
    acc = 100 * correct / total if total else 0

    print(f"\n=== Eval Intent Classification ===\n")
    print(f"Acurácia: {correct}/{total} ({acc:.1f}%)\n")

    # Por classe
    by_class: dict[str, list[tuple[str, str, str]]] = {}
    for text, exp, got in results:
        by_class.setdefault(exp, []).append((text, exp, got))

    print("Por classe:")
    for task_type in sorted(by_class.keys()):
        items = by_class[task_type]
        c = sum(1 for _, exp, got in items if exp == got)
        n = len(items)
        pct = 100 * c / n if n else 0
        status = "[OK]" if c == n else "[X]"
        print(f"  {status} {task_type}: {c}/{n} ({pct:.0f}%)")

    # Falhas
    failures = [(t, exp, got) for t, exp, got in results if exp != got]
    if failures:
        print(f"\nFalhas ({len(failures)}):")
        for text, exp, got in failures[:15]:
            print(f"  esperado={exp} got={got}")
            print(f"    \"{text[:60]}{'...' if len(text) > 60 else ''}\"")
        if len(failures) > 15:
            print(f"  ... e mais {len(failures) - 15}")


def main():
    ap = argparse.ArgumentParser(description="Eval de classificação de intenção")
    ap.add_argument("--mock", action="store_true", help="Usa mock (sem chamadas reais à API)")
    ap.add_argument("--llm", choices=["openai", "anthropic"], help="Provider do LLM")
    args = ap.parse_args()
    asyncio.run(run_eval(mock=args.mock, llm_provider=args.llm))


if __name__ == "__main__":
    main()
