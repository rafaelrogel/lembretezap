"""List tool: add, list, remove, feito (mark done), shuffle per user. Persistência imediata em SQLite, IDs estáveis, auditoria."""

import json
import random
from typing import Any

from sqlalchemy import func

from zapista.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import List, ListItem, AuditLog, Project
from backend.sanitize import sanitize_string, MAX_LIST_NAME_LEN, MAX_ITEM_TEXT_LEN
from backend.list_item_correction import suggest_correction
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.list_history import get_frequent_items
from backend.user_store import get_user_timezone


class ListTool(Tool):
    """Manage lists per user: add item, list items, remove, mark done (feito)."""

    def __init__(self, scope_provider=None, scope_model: str = ""):
        self._chat_id = ""
        self._scope_provider = scope_provider
        self._scope_model = (scope_model or "").strip()

    def set_context(self, channel: str, chat_id: str) -> None:
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "list"

    @property
    def description(self) -> str:
        return (
            "Manage user lists. action: add (list_name, item), list (list_name), remove (list_name, item_id), "
            "feito (list_name, item_id to mark done), habitual (list_name: add frequent items from history), "
            "shuffle (list_name: randomize order of items in place)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "feito", "habitual", "shuffle"],
                    "description": "add | list | remove | feito | habitual | shuffle (randomize list order)",
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
                list_clean = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
                item_clean = sanitize_string(item_text or "", MAX_ITEM_TEXT_LEN)
                corrected = await suggest_correction(
                    list_clean, item_clean,
                    self._scope_provider, self._scope_model,
                    max_len=MAX_ITEM_TEXT_LEN,
                )
                if corrected:
                    item_clean = sanitize_string(corrected, MAX_ITEM_TEXT_LEN)
                return self._add(db, user.id, list_clean, item_clean)
            if action == "habitual":
                return await self._habitual(db, user.id, list_name or "")
            if action == "list":
                return self._list(db, user.id, list_name)
            if action == "remove":
                return self._remove(db, user.id, list_name, item_id)
            if action == "feito":
                if (not list_name or not list_name.strip()) and item_id is not None:
                    list_name = self._resolve_list_by_item_id(db, user.id, item_id)
                    if not list_name:
                        return f"Item {item_id} não encontrado. Use /feito nome_da_lista {item_id} se souber a lista."
                return self._feito(db, user.id, list_name, item_id)
            if action == "shuffle":
                return self._shuffle(db, user.id, list_name or "")
            return f"Unknown action: {action}"
        finally:
            db.close()

    def _add(self, db, user_id: int, list_name: str, item_text: str) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        item_text = sanitize_string(item_text or "", MAX_ITEM_TEXT_LEN)
        if not list_name or not item_text:
            return "Error: list_name and item_text required for add"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            proj = db.query(Project).filter(Project.user_id == user_id, Project.name == list_name).first()
            lst = List(user_id=user_id, name=list_name, project_id=proj.id if proj else None)
            db.add(lst)
            db.flush()
        max_pos = (
            db.query(func.max(ListItem.position))
            .filter(ListItem.list_id == lst.id)
            .scalar()
            or 0
        )
        item = ListItem(list_id=lst.id, text=item_text, position=max_pos + 1)
        db.add(item)
        db.flush()  # obter item.id antes do commit
        audit_payload = json.dumps({"list_name": list_name, "item_text": item_text, "item_id": item.id})
        db.add(AuditLog(user_id=user_id, action="list_add", resource=list_name, payload_json=audit_payload))
        db.commit()
        return f"Adicionado a '{list_name}': {item_text} (id: {item.id})"

    async def _habitual(self, db, user_id: int, list_name: str) -> str:
        """Adiciona itens habituais à lista. Mimo sugere com base no contexto (dia, época); fallback: top frequentes."""
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        if not list_name:
            return "Indica o nome da lista. Ex: /list mercado habitual"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            lst = List(user_id=user_id, name=list_name)
            db.add(lst)
            db.flush()
        pending_items = [
            i.text.strip()
            for i in db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.done == False).all()
        ]
        pending_texts = {t.lower() for t in pending_items}
        freq = get_frequent_items(db, self._chat_id, weeks=4, top_per_list=12)
        items_for_list = freq.get(list_name, [])
        # Candidatos: frequentes que ainda não estão pendentes
        candidates = [
            (text, count)
            for text, count in items_for_list
            if text and text.strip() and text.strip().lower() not in pending_texts
        ]
        if not candidates:
            return f"Lista \"{list_name}\": não há itens habituais novos para adicionar (já tens tudo ou sem histórico)."

        # Mimo sugere com base no contexto (se disponível); já valida contra candidatos
        to_add: list[str] = []
        if self._scope_provider and self._scope_model:
            suggested = await self._ask_mimo_suggestion(
                db=db,
                list_name=list_name,
                candidates=[t for t, _ in candidates],
                pending=pending_items,
            )
            if suggested:
                to_add = [s for s in suggested if s and s.strip().lower() not in pending_texts][:6]

        # Fallback: top por frequência
        if not to_add:
            for text, _ in candidates[:6]:
                item_clean = sanitize_string(text, MAX_ITEM_TEXT_LEN)
                if item_clean and item_clean.lower() not in pending_texts:
                    to_add.append(item_clean)
                    pending_texts.add(item_clean.lower())

        added: list[str] = []
        next_pos = (
            db.query(func.max(ListItem.position)).filter(ListItem.list_id == lst.id).scalar() or 0
        ) + 1
        for item_clean in to_add:
            if not item_clean:
                continue
            item = ListItem(list_id=lst.id, text=item_clean, position=next_pos)
            next_pos += 1
            db.add(item)
            db.flush()
            audit_payload = json.dumps({"list_name": list_name, "item_text": item_clean, "item_id": item.id})
            db.add(AuditLog(user_id=user_id, action="list_add", resource=list_name, payload_json=audit_payload))
            added.append(item_clean)
        db.commit()
        return f"Adicionei o habitual a \"{list_name}\": {', '.join(added)}."

    async def _ask_mimo_suggestion(
        self,
        db,
        list_name: str,
        candidates: list[str],
        pending: list[str],
    ) -> list[str]:
        """Mimo sugere até 6 itens da lista de candidatos, considerando contexto (dia, época, pendentes)."""
        if not candidates or not self._scope_provider or not self._scope_model:
            return []
        try:
            try:
                tz_iana = get_user_timezone(db, self._chat_id)
                z = ZoneInfo(tz_iana) if tz_iana else ZoneInfo("UTC")
            except Exception:
                z = ZoneInfo("UTC")
            now = datetime.now(z)
            weekday = now.strftime("%A")  # Monday, Tuesday...
            date_str = now.strftime("%Y-%m-%d")
            month = now.month
            season = "verão" if month in (12, 1, 2) else "outono" if month in (3, 4, 5) else "inverno" if month in (6, 7, 8) else "primavera"

            data = (
                f"Lista: {list_name}\n"
                f"Dia: {weekday}, data: {date_str}, estação: {season}\n"
                f"Já pendentes na lista: {', '.join(pending[:10]) or '(vazia)'}\n"
                f"Candidatos (itens frequentes das últimas 4 semanas): {', '.join(candidates[:15])}"
            )
            instruction = (
                "O utilizador quer adicionar o 'habitual' a esta lista. Com base no contexto (dia da semana, estação, "
                "o que já está pendente), sugere até 6 itens dos CANDIDATOS para adicionar. Responde APENAS com os "
                "textos separados por vírgula, na ordem de prioridade. Usa exatamente o texto dos candidatos. Sem explicação."
            )
            r = await self._scope_provider.chat(
                messages=[{"role": "user", "content": f"{instruction}\n\n{data}"}],
                model=self._scope_model,
                max_tokens=120,
                temperature=0.3,
            )
            out = (r.content or "").strip().strip(".'\"")
            if not out:
                return []
            # Parse: "leite, pão, manteiga" -> ["leite", "pão", "manteiga"]
            parts = [p.strip() for p in out.split(",") if p.strip()]
            cand_lower = {c.strip().lower(): c.strip() for c in candidates}
            result: list[str] = []
            for p in parts[:6]:
                key = p.strip().lower()
                if key in cand_lower:
                    result.append(cand_lower[key])
            return result
        except Exception:
            return []

    def _list(self, db, user_id: int, list_name: str) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN) if list_name else ""
        if not list_name:
            lists = db.query(List).filter(List.user_id == user_id).all()
            if not lists:
                return "Nenhuma lista. Use /list nome add item para criar."
            return "Listas: " + ", ".join(l.name for l in lists)
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.done == False)
            .order_by(ListItem.position, ListItem.id)
            .all()
        )
        if not items:
            return f"Lista '{list_name}' vazia."
        lines = [f"{i.id}. {i.text}" for i in items]
        return f"Lista **{list_name}**:\n" + "\n".join(lines)

    def _remove(self, db, user_id: int, list_name: str, item_id: int | None) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        if not list_name or item_id is None:
            return "Error: list_name and item_id required for remove"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        if not item:
            return f"Item {item_id} não encontrado."
        item_text = item.text
        item.done = True  # soft-delete: mantém no DB para auditoria/recuperação
        payload = json.dumps({"list_name": list_name, "item_id": item_id, "item_text": item_text})
        db.add(AuditLog(user_id=user_id, action="list_remove", resource=f"{list_name}#{item_id}", payload_json=payload))
        db.commit()
        return f"Removido item {item_id} de '{list_name}'."

    def _resolve_list_by_item_id(self, db, user_id: int, item_id: int) -> str | None:
        """Encontra o nome da lista que contém o item com este id (do utilizador)."""
        item = db.query(ListItem).join(List).filter(List.user_id == user_id, ListItem.id == item_id).first()
        return item.list_ref.name if item and item.list_ref else None

    def _shuffle(self, db, user_id: int, list_name: str) -> str:
        """Embaralha a ordem dos itens na lista (in-place)."""
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        if not list_name:
            return "Indica o nome da lista. Ex: embaralha lista summer_hits"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.done == False)
            .order_by(ListItem.position, ListItem.id)
            .all()
        )
        if not items:
            return f"Lista '{list_name}' vazia."
        if len(items) == 1:
            return f"Lista '{list_name}' tem só 1 item; não há o que embaralhar."
        order = list(range(len(items)))
        random.shuffle(order)
        for i, item in enumerate(items):
            item.position = order[i]
        payload = json.dumps({"list_name": list_name, "item_count": len(items)})
        db.add(AuditLog(user_id=user_id, action="list_shuffle", resource=list_name, payload_json=payload))
        db.commit()
        return f"Lista '{list_name}' embaralhada ({len(items)} itens)."

    def _feito(self, db, user_id: int, list_name: str, item_id: int | None) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        if not list_name or item_id is None:
            return "Error: list_name and item_id required for feito"
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            return f"Lista '{list_name}' não existe."
        item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        if not item:
            return f"Item {item_id} não encontrado."
        item_text = item.text
        item.done = True  # soft-delete: mantém no DB para auditoria (sem auto-limpeza)
        payload = json.dumps({"list_name": list_name, "item_id": item_id, "item_text": item_text})
        db.add(AuditLog(user_id=user_id, action="list_feito", resource=f"{list_name}#{item_id}", payload_json=payload))
        db.commit()
        return f"Feito! Item {item_id} removido de '{list_name}'."
