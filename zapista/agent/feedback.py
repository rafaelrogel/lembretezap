"""
Coletor de feedback para classificação de intenção (NLU).

Loga predições em JSONL para debug e para enriquecer o dataset
quando houver correções do usuário ou anotação manual.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from zapista.config.domain_ontology import IntentClassification, TaskType


class IntentFeedbackCollector:
    def __init__(self, feedback_dir: Path | str | None = None):
        self.feedback_dir = Path(feedback_dir or "workspace/nlu_feedback")
        self.feedback_dir.mkdir(parents=True, exist_ok=True)

    def log_prediction(
        self,
        user_message: str,
        predicted: IntentClassification,
        actual: Optional[TaskType] = None,
    ) -> None:
        """Salva predição para análise posterior ou retreinamento."""
        entities_serialized = [
            e.model_dump(mode="json") for e in predicted.entities
        ]
        if predicted.follow_up_suggestion:
            fus = predicted.follow_up_suggestion
            follow_up_serialized = {
                "task_type": fus.task_type.value,
                "entities": [e.model_dump(mode="json") for e in fus.entities],
                "prompt_text": fus.prompt_text,
            }
        else:
            follow_up_serialized = None

        entry = {
            "timestamp": datetime.now().isoformat(),
            "message": user_message,
            "predicted_type": predicted.task_type.value,
            "confidence": predicted.confidence,
            "entities": entities_serialized,
            "requires_clarification": predicted.requires_clarification,
            "clarification_options": predicted.clarification_options,
            "follow_up_suggestion": follow_up_serialized,
            "actual_type": actual.value if actual else None,
            "correct": actual == predicted.task_type if actual is not None else None,
        }

        filepath = self.feedback_dir / f"predictions_{datetime.now().strftime('%Y%m')}.jsonl"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def generate_training_data(self) -> Dict[str, List[str]]:
        """
        Extrai casos com rótulo correto para adicionar ao dataset.

        Útil quando há correções do usuário ou anotação manual.
        """
        correct_by_type: Dict[str, List[str]] = {}

        for filepath in self.feedback_dir.glob("*.jsonl"):
            with open(filepath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("correct") is True:
                        task_type = entry["predicted_type"]
                        if task_type not in correct_by_type:
                            correct_by_type[task_type] = []
                        msg = entry.get("message", "")
                        if msg and msg not in correct_by_type[task_type]:
                            correct_by_type[task_type].append(msg)

        return correct_by_type
