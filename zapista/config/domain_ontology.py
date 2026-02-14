from __future__ import annotations

from enum import Enum
from typing import Optional, List, Any
from pydantic import BaseModel, Field, model_validator


class TaskType(str, Enum):
    REMINDER = "reminder"  # ação pontual futura
    EVENT = "event"  # calendário + participantes
    RECURRING_TASK = "recurring"  # cron pattern
    LIST = "list"  # coleção de itens
    QUERY = "query"  # busca informação
    MEDIA_RECOMMENDATION = "media"  # filme/série/livro
    GENERAL = "general"  # conversa geral


class EntityType(str, Enum):
    DATETIME = "datetime"
    ITEM_NAME = "item_name"
    CATEGORY = "category"
    LOCATION = "location"
    PERSON = "person"
    MEDIA_TITLE = "media_title"
    QUANTITY = "quantity"
    RECURRENCE = "recurrence"


class ExtractedEntity(BaseModel):
    type: EntityType
    value: str
    normalized_value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0)
    span: Optional[tuple[int, int]] = None  # posição no texto


class FollowUpSuggestion(BaseModel):
    """Sugestão de ação secundária após executar a principal (ex: lembrete + perguntar se adiciona itens na lista)."""

    task_type: TaskType
    entities: List[ExtractedEntity] = Field(default_factory=list)
    prompt_text: Optional[str] = None  # ex: "Quer adicionar carne do sol e farinha na lista de compras?"


class IntentClassification(BaseModel):
    task_type: TaskType
    confidence: float = Field(ge=0.0, le=1.0)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    raw_text: str = ""
    requires_clarification: bool = False
    clarification_options: Optional[List[str]] = None  # IDs: ["reminder", "list"], etc.
    follow_up_suggestion: Optional[FollowUpSuggestion] = None  # ação secundária sugerida

    @model_validator(mode="after")
    def derive_clarification_from_confidence(self) -> "IntentClassification":
        """Se confidence < 0.7, força requires_clarification=True."""
        if self.confidence < 0.7 and not self.requires_clarification:
            object.__setattr__(self, "requires_clarification", True)
        return self
