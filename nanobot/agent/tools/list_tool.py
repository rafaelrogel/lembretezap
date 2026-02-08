"""List tool: add, list, remove, feito (mark done / delete) per user."""

from typing import Any

from nanobot.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import List, ListItem, AuditLog


class ListTool(Tool):
    """Manage lists per user: add item, list items, remove, mark done (feito)."""

    def __init__(self):
        self._chat_id = ""  # phone for WhatsApp

    def set_context(self, channel: str, chat_id: str) -> None:
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "list"

    @property
    def description(self) -> str:
        return (
            "Manage user lists. action: add (list_name, item), list (list_name), remove (list_name, item_id), "
            "feito (list_name, item_id to mark done and delete)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "feito"],
                    "description": "add | list | remove | feito",
                },
                "list_name": {"type": "string", "description": "List name (e.g. mercado, pendentes)"},
                "item_text": {"type": "string", "description": "Item text (for add)"},
                "item_id": {"type": "integer", "description": "Item id (for remove/feito)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        list_name: str = "",
        item_text: str = "",
        item_id: int | None = None,
        **kwargs: Any,
    ) -> str:
        if not self._chat_id:
            return "Error: no user context (chat_id)"
        db = SessionLocal()
        try:
            user = get_or_create_user(db, self._chat_id)
            if action == "add":
                return self._add(db, user.id, list_name, item_text)
            if action == "list":
                return self._list(db, user.id, list_name)
            if action == "remove":
                return self._remove(db, user.id, list_name, item_id)
            if action == "feito":
                return self._feito(db, user.id, list_name, item_id)
            return f"Unknown action: {action}"
        finally:
            db.close()

    def _add(self, db, user_id: int, list_name: str, item_text: str) -> str:
        if not list_name or not item_text:
            return "Error: list_name and item_text required for add"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name.strip()).first()
        if not lst:
            lst = List(user_id=user_id, name=list_name.strip())
            db.add(lst)
            db.flush()
        item = ListItem(list_id=lst.id, text=item_text.strip())
        db.add(item)
        db.add(AuditLog(user_id=user_id, action="list_add", resource=list_name))
        db.commit()
        return f"Adicionado a '{list_name}': {item_text.strip()} (id: {item.id})"

    def _list(self, db, user_id: int, list_name: str) -> str:
        if not list_name:
            # List all list names
            lists = db.query(List).filter(List.user_id == user_id).all()
            if not lists:
                return "Nenhuma lista. Use /list nome add item para criar."
            return "Listas: " + ", ".join(l.name for l in lists)
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name.strip()).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        items = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.done == False).order_by(ListItem.id).all()
        if not items:
            return f"Lista '{list_name}' vazia."
        lines = [f"{i.id}. {i.text}" for i in items]
        return f"Lista **{list_name}**:\n" + "\n".join(lines)

    def _remove(self, db, user_id: int, list_name: str, item_id: int | None) -> str:
        if not list_name or item_id is None:
            return "Error: list_name and item_id required for remove"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name.strip()).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        if not item:
            return f"Item {item_id} não encontrado."
        db.delete(item)
        db.add(AuditLog(user_id=user_id, action="list_remove", resource=f"{list_name}#{item_id}"))
        db.commit()
        return f"Removido item {item_id} de '{list_name}'."

    def _feito(self, db, user_id: int, list_name: str, item_id: int | None) -> str:
        if not list_name or item_id is None:
            return "Error: list_name and item_id required for feito"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name.strip()).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        if not item:
            return f"Item {item_id} não encontrado."
        db.delete(item)  # delete after confirm (no history for MVP)
        db.add(AuditLog(user_id=user_id, action="list_feito", resource=f"{list_name}#{item_id}"))
        db.commit()
        return f"Feito! Item {item_id} removido de '{list_name}'."
