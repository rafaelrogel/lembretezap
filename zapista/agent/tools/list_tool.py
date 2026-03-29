"""List tool: add, list, remove, feito (mark done), shuffle per user. Persistência imediata em SQLite, IDs estáveis, auditoria."""

import json
import random
from typing import Any

from backend.logger import get_logger
logger = get_logger(__name__)
from sqlalchemy import func

from zapista.agent.tools.base import Tool
from backend.database import SessionLocal
from backend.user_store import get_or_create_user
from backend.models_db import User, List, ListItem, AuditLog, Project
from backend.sanitize import sanitize_string, MAX_LIST_NAME_LEN, MAX_LIST_ITEM_TEXT_LEN, looks_like_confidential_data
from backend.list_item_correction import suggest_correction
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.list_history import get_frequent_items
from backend.user_store import get_user_timezone
from backend.locale import CONFIRM_ITEMS_ADDED_TO_LIST


class ListTool(Tool):
    """Manage lists per user: add item, list items, remove, mark done (feito)."""

    def __init__(self, scope_provider=None, scope_model: str = ""):
        self._channel = ""
        self._chat_id = ""
        self._phone_for_locale = None
        self._scope_provider = scope_provider
        self._scope_model = (scope_model or "").strip()

    def set_context(self, channel: str, chat_id: str, phone_for_locale: str | None = None) -> None:
        self._channel = channel
        self._chat_id = chat_id
        self._phone_for_locale = phone_for_locale

    def _get_lang(self) -> str:
        try:
            from backend.database import SessionLocal
            from backend.user_store import get_user_language
            db = SessionLocal()
            try:
                return get_user_language(db, self._chat_id, self._phone_for_locale) or "pt-BR"
            finally:
                db.close()
        except Exception:
            return "pt-BR"

    @property
    def name(self) -> str:
        return "list"

    @property
    def description(self) -> str:
        return (
            "Manage user lists. Always use this tool when the user asks to create a list, add items (e.g. books, recipes), or show lists; do not say the system is broken without calling the tool first. "
            "Actions: add (list_name, item_text — REQUIRED: never call add without a non-empty item_text, ask the user what to add first; "
            "IMPORTANT: when adding multiple items, call add once per item — never pack multiple items into a single item_text), "
            "list (list_name), remove (list_name, item_id), "
            "feito (list_name, item_id to mark done), habitual (list_name), shuffle (list_name)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove", "delete_list", "delete_all", "feito", "habitual", "shuffle"],
                    "description": "add | list | remove | delete_list (DESTROY SINGLE LIST) | delete_all (NUKE ALL LISTS) | feito | habitual | shuffle",
                },
                "list_name": {"type": "string", "description": "List name (e.g. mercado, pendentes)"},
                "item_text": {"type": "string", "description": "Item text (for add)"},
                "item_id": {"type": "integer", "description": "Item id (for remove/feito)"},
                "no_split": {"type": "boolean", "description": "If true, do not split item_text by commas even if short."},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        list_name: str = "",
        item_text: str = "",
        item_id: int | None = None,
        no_split: bool = False,
        **kwargs: Any,
    ) -> str:
        if not self._chat_id:
            return "Error: no user context (chat_id)"
        db = SessionLocal()
        try:
            user = get_or_create_user(db, self._chat_id)
            # Save last_list_name for context (only if list_name was provided or inferred)
            if list_name and list_name.strip():
                ln_norm = self._normalize_list_name(list_name)
                if ln_norm:
                    user.last_list_name = ln_norm
                    db.commit()

            if action == "add":
                list_name_requested = list_name or ""
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name_requested)
                
                if not list_clean and user.last_list_name:
                    list_clean = user.last_list_name

                item_clean = sanitize_string(item_text or "", MAX_LIST_ITEM_TEXT_LEN, allow_newline=True)
                corrected = await suggest_correction(
                    list_clean or list_name_requested or "mercado", item_clean,
                    self._scope_provider, self._scope_model,
                    max_len=MAX_LIST_ITEM_TEXT_LEN,
                )
                if corrected:
                    item_clean = sanitize_string(corrected, MAX_LIST_ITEM_TEXT_LEN, allow_newline=True)
                
                result = self._add(db, user.id, list_clean or list_name_requested or "mercado", item_clean, no_split=no_split)
                return result

            if action == "list":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                res = self._list(db, user.id, list_clean or list_name)
                if list_clean:
                    user.last_list_name = list_clean
                    db.commit()
                return res
            
            if action == "remove":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                res = self._remove(db, user.id, list_clean or list_name, item_id, item_text)
                return res

            if action == "feito":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                if not list_clean and item_id is not None:
                    list_clean = self._resolve_list_by_item_id(db, user.id, item_id)
                res = self._feito(db, user.id, list_clean or list_name, item_id, item_text)
                return res

            if action == "delete_list":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                return self._delete_list(db, user.id, list_clean or list_name)

            if action == "delete_all":
                return self._delete_all_lists(db, user.id)

            if action == "habitual":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                return await self._habitual(db, user.id, list_clean or list_name or "")

            if action == "shuffle":
                list_clean = self._resolve_list_name_fuzzy(db, user.id, list_name)
                return self._shuffle(db, user.id, list_clean or list_name or "")
            return f"Unknown action: {action}"
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            logger.error("list_tool_execute_failed", extra={"extra": {
                "action": action,
                "list_name": list_name,
                "chat_id": self._chat_id,
                "error": str(e)
            }})
            from backend.locale import LIST_TECH_ERROR
            lang = self._get_lang()
            return LIST_TECH_ERROR.get(lang, LIST_TECH_ERROR["en"])
        finally:
            db.close()

    @staticmethod
    def _split_items(item_text: str) -> list[str]:
        """
        Divide texto em múltiplos itens quando separados por vírgula, nova linha ou conectores.
        """
        import re
        text = item_text.strip()
        # Primeiro dividir por novas linhas (user colou lista)
        # Se contiver novas linhas, assumimos que cada linha é um item
        if "\n" in text:
            lines = [p.strip() for p in text.split("\n") if p.strip()]
            all_parts = []
            for line in lines:
                # Cada linha pode ainda ter vírgulas
                norm = re.sub(r"\s+(?:e|y|and)\s+", ", ", line, flags=re.IGNORECASE)
                parts = [p.strip() for p in re.split(r",\s*", norm) if p.strip()]
                all_parts.extend(parts)
            return all_parts

        # Se não tem nova linha, dividir por vírgula e conectores
        normalized = re.sub(r"\s+(?:e|y|and)\s+", ", ", text, flags=re.IGNORECASE)
        parts = [p.strip() for p in re.split(r",\s*", normalized) if p.strip()]
        if len(parts) <= 1:
            return [text]
        # Só dividir se as partes forem razoavelmente curtas
        if all(len(p) <= 200 for p in parts):
            return parts
        return [text]

    @staticmethod
    def _normalize_for_dedup(text: str) -> str:
        """Lowercase, sem espaços extras e tenta normalizar plural básico (ex: ovos -> ovo)."""
        import unicodedata
        s = (text or "").lower().strip()
        s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
        # Heurística simples de plural (pt/es): termina em 's' e tem pelo menos 3 chars
        if len(s) > 3 and s.endswith("s"):
            # Só remove o 's' se não for uma palavra que normalmente termina em 's' (ex: tênis, ônibus - simplificado)
            if not s.endswith(("ss", "is", "us")):
                return s[:-1]
        return s

    def _resolve_list_name_fuzzy(self, db, user_id: int, name: str) -> str:
        """Resolve o nome da lista considerando aliases e existência.
        Ex: se user pede 'compras' mas só existe 'mercado', retorna 'mercado'.
        """
        if not name:
            return ""
        name = self._normalize_list_name(name)
        if not name:
            return ""
        
        # 1. Tentar match exato (insensível a maiúsculas na DB)
        from backend.models_db import List
        lst = db.query(List).filter(List.user_id == user_id, func.lower(List.name) == name.lower()).first()
        if lst:
            return lst.name
        
        # 2. Se não existe, tentar aliases comuns
        _ALIASES = {
            # Shopping / Mercado
            "compras": "mercado", "comprar": "mercado", "mercado": "compras",
            "shopping": "mercado", "grocery": "mercado", "groceries": "mercado", "market": "mercado",
            # Filmes / Movies
            "filme": "filmes", "filmes": "filmes",
            "movie": "filmes", "movies": "filmes", "film": "filmes", "films": "filmes",
            "película": "filmes", "películas": "filmes", "pelicula": "filmes", "peliculas": "filmes",
            # Livros / Books
            "livro": "livros", "livros": "livros",
            "book": "livros", "books": "livros",
            "libro": "livros", "libros": "livros",
            # Músicas / Songs
            "musica": "músicas", "música": "músicas", "musicas": "músicas", "músicas": "músicas",
            "song": "músicas", "songs": "músicas", "music": "músicas",
            "canción": "músicas", "canciones": "músicas",
            # Séries
            "série": "séries", "séries": "séries", "serie": "séries", "series": "séries",
            # Jogos / Games
            "jogo": "jogos", "jogos": "jogos",
            "game": "jogos", "games": "jogos",
            "juego": "jogos", "juegos": "jogos",
            # Receitas
            "receita": "receitas", "receitas": "receitas",
            "recipe": "receitas", "recipes": "receitas",
            "receta": "receitas", "recetas": "receitas",
            # Notas / Notes
            "nota": "notas", "notas": "notas",
            "note": "notas", "notes": "notas",
        }
        alias = _ALIASES.get(name.lower())
        if alias:
            lst_alias = db.query(List).filter(List.user_id == user_id, func.lower(List.name) == alias.lower()).first()
            if lst_alias:
                return lst_alias.name
        
        # 3. Se ainda não encontrou, tentar remover "lista" / "list" / "la lista" prefixos
        # Ex: "a lista detergente" -> "detergente"
        stripped_name = self._normalize_list_name(name)
        if stripped_name.lower() != name.lower():
            lst_stripped = db.query(List).filter(List.user_id == user_id, func.lower(List.name) == stripped_name.lower()).first()
            if lst_stripped:
                return lst_stripped.name

        # 4. Se ainda não encontrou, retornar o original
        return name

    @staticmethod
    def _normalize_list_name(name: str) -> str:
        """Strip connector words and articles/prefixes mistakenly used as list names across 4 languages."""
        import re
        if not name:
            return ""
        
        # 1. Strip common connector-only names
        _CONNECTORS = {
            # PT
            "chamada", "chamado", "denominada", "denominado", "nomeada", "nomeado", "de", "do", "da",
            # ES
            "llamada", "llamado", "denominada", "denominado", "nombrada", "nombrado", "con", "el", "la",
            # EN
            "called", "named", "with", "the",
            # FR
            "nommee", "nommée", "nomme", "nommé", "appelee", "appelée", "appele", "appelé", "avec", "le",
            # Misc
            "ai", "aí", "ahi", "ahí", "ali", "allí", "here", "there", "aqui", "aquí",
            "lá", "alla", "allá", "it", "esto", "eso", "isto", "isso"
        }
        stripped = name.strip().lower()
        if stripped in _CONNECTORS:
            return ""
        
        # 2. Cleanup "the list of X" or "a lista de X" patterns
        # PT/BR: "a lista de compras" -> "compras", "lista do mercado" -> "mercado"
        # ES: "la lista de compras" -> "compras"
        # EN: "the shopping list" -> "shopping"
        
        # Pattern match for prefixes
        # Portuguese: a lista de, o mercado de, lista de, as listas de
        # Spanish: la lista de, las listas de, el mercado de
        # English: the list of, a list of, the market of, list of
        clean = name.strip()
        
        # Remove common "list" prefixes in 4 languages
        prefixes = [
            # Portuguese
            r"^(?:as?\s+)?listas?\s+(?:de|do|da|dos|das)\s+",
            r"^(?:as?\s+)?listas?\s+",
            r"^(?:os?\s+)?mercados?\s+(?:de|do|da)\s+",
            # Spanish
            r"^(?:las?\s+)?listas?\s+(?:de|del)\s+",
            r"^(?:las?\s+)?listas?\s+",
            r"^(?:el\s+)?mercados?\s+(?:de|del)\s+",
            # English
            r"^(?:the\s+|a\s+)?lists?\s+(?:of|for)\s+",
            r"^(?:the\s+|a\s+)?lists?\s+",
            r"^(?:the\s+)?markets?\s+(?:of|for)\s+",
        ]
        
        for p in prefixes:
            new_clean = re.sub(p, "", clean, flags=re.IGNORECASE)
            if new_clean != clean:
                clean = new_clean
                break
        
        # Also remove leading articles if they survive
        articles = [
            r"^(?:as?|os?|the|an?|las?|el|los)\s+"
        ]
        for p in articles:
            clean = re.sub(p, "", clean, flags=re.IGNORECASE)
            
        return clean.strip() or name.strip()

    def _add(self, db, user_id: int, list_name: str, item_text: str, no_split: bool = False) -> str:
        list_name = self._normalize_list_name(sanitize_string(list_name or "", MAX_LIST_NAME_LEN))
        
        # Fallback to last used list if name is empty (connector)
        if not list_name:
            user = db.query(User).filter(User.id == user_id).first()
            if user and user.last_list_name:
                list_name = user.last_list_name
        
        item_text = sanitize_string(item_text or "", MAX_LIST_ITEM_TEXT_LEN, allow_newline=True)
        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_ADD
            lang = self._get_lang()
            return LIST_NAME_REQUIRED_ADD.get(lang, LIST_NAME_REQUIRED_ADD["en"])
        if not item_text or not item_text.strip():
            from backend.locale import LIST_EMPTY_ITEM_ERROR
            try:
                from backend.database import SessionLocal
                from backend.user_store import get_user_language
                _db = SessionLocal()
                try:
                    _lg = get_user_language(_db, self._chat_id) or "pt-BR"
                finally:
                    _db.close()
            except Exception:
                _lg = "pt-BR"
            return LIST_EMPTY_ITEM_ERROR.get(_lg, LIST_EMPTY_ITEM_ERROR["en"]).format(list_name=list_name)
        if looks_like_confidential_data(item_text):
            from backend.locale import LIST_PRIVACY_WARNING
            lang = self._get_lang()
            return LIST_PRIVACY_WARNING.get(lang, LIST_PRIVACY_WARNING["en"])

        # Auto-split: se LLM passou múltiplos itens numa string, dividir e adicionar cada um
        if no_split:
            items_to_add = [item_text]
        else:
            items_to_add = self._split_items(item_text)
        
        # Obter idioma para confirmação
        try:
            from backend.user_store import get_user_language
            _lg = get_user_language(db, self._chat_id) or "pt-BR"
        except Exception:
            _lg = "pt-BR"

        added_count = 0
        for single_item in items_to_add:
            single_clean = sanitize_string(single_item, MAX_LIST_ITEM_TEXT_LEN)
            if single_clean:
                if self._add_single(db, user_id, list_name, single_clean):
                    added_count += 1
        
        # Obter contagem total de itens pendentes
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        total_count = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.done.is_(False)).count() if lst else 0
        
        return CONFIRM_ITEMS_ADDED_TO_LIST.get(_lg, CONFIRM_ITEMS_ADDED_TO_LIST["en"]).format(
            list_name=list_name, count=total_count
        )

    def _add_single(self, db, user_id: int, list_name: str, item_text: str) -> bool:
        """Adiciona um único item à lista (uso interno; deduplica). Retorna True se adicionou."""
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            proj = db.query(Project).filter(Project.user_id == user_id, Project.name == list_name).first()
            lst = List(user_id=user_id, name=list_name, project_id=proj.id if proj else None)
            db.add(lst)
            db.flush()
        
        # Deduplicação: verifica se já existe item pendente idêntico ou muito similar
        norm_new = self._normalize_for_dedup(item_text)
        existing_items = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.done.is_(False)).all()
        for ex in existing_items:
            if self._normalize_for_dedup(ex.text) == norm_new:
                return False

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
        return True

    async def _habitual(self, db, user_id: int, list_name: str) -> str:
        """Adiciona itens habituais à lista. Mimo sugere com base no contexto (dia, época); fallback: top frequentes."""
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_HABITUAL
            lang = self._get_lang()
            return LIST_NAME_REQUIRED_HABITUAL.get(lang, LIST_NAME_REQUIRED_HABITUAL["en"])
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
            from backend.locale import LIST_NO_HABITUAL
            lang = self._get_lang()
            return LIST_NO_HABITUAL.get(lang, LIST_NO_HABITUAL["en"]).format(list_name=list_name)

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
                item_clean = sanitize_string(text, MAX_LIST_ITEM_TEXT_LEN)
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
        from backend.locale import LIST_HABITUAL_ADDED
        lang = self._get_lang()
        return LIST_HABITUAL_ADDED.get(lang, LIST_HABITUAL_ADDED["en"]).format(list_name=list_name, items=', '.join(added))

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
                from backend.timezone import phone_to_default_timezone
                tz_iana = get_user_timezone(db, self._chat_id, self._phone_for_locale) or phone_to_default_timezone(self._phone_for_locale or self._chat_id) or "UTC"
                z = ZoneInfo(tz_iana) if tz_iana else ZoneInfo("UTC")
            except Exception:
                z = ZoneInfo("UTC")
            try:
                from zapista.clock_drift import get_effective_time
                _now_ts = get_effective_time()
            except Exception:
                import time
                _now_ts = time.time()
            now = datetime.fromtimestamp(_now_ts, tz=z)
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
            # Parse: "[item A], [item B], [item C]" -> ["[item A]", "[item B]", "[item C]"]
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
        lang = self._get_lang()
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN) if list_name else ""
        if not list_name:
            lists = db.query(List).filter(List.user_id == user_id).all()
            if not lists:
                from backend.locale import LIST_NO_LISTS
                return LIST_NO_LISTS.get(lang, LIST_NO_LISTS["en"])
            from backend.locale import LIST_ALL_LISTS
            return LIST_ALL_LISTS.get(lang, LIST_ALL_LISTS["en"]).format(names=", ".join(l.name for l in lists))
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            from backend.locale import LIST_NOT_FOUND
            return LIST_NOT_FOUND.get(lang, LIST_NOT_FOUND["en"]).format(list_name=list_name)
        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.done == False)
            .order_by(ListItem.position, ListItem.id)
            .all()
        )
        if not items:
            from backend.locale import LIST_EMPTY
            return LIST_EMPTY.get(lang, LIST_EMPTY["en"]).format(list_name=list_name)
        lines = [f"{idx}. {i.text} (id:{i.id})" for idx, i in enumerate(items, 1)]
        from backend.locale import LIST_HEADER
        return LIST_HEADER.get(lang, LIST_HEADER["en"]).format(list_name=list_name) + "\n" + "\n".join(lines)

    def _remove(self, db, user_id: int, list_name: str, item_id: int | None = None, item_text: str | None = None) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        lang = self._get_lang()
        if not list_name and item_id:
            # Tenta inferir lista pelo item_id
            list_name = self._resolve_list_by_item_id(db, user_id, item_id)

        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_REMOVE
            return LIST_NAME_REQUIRED_REMOVE.get(lang, LIST_NAME_REQUIRED_REMOVE["en"])

        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            from backend.locale import LIST_NOT_FOUND
            return LIST_NOT_FOUND.get(lang, LIST_NOT_FOUND["en"]).format(list_name=list_name)

        item = None
        if item_id is not None:
            item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        elif item_text:
            # Procura por texto (exato ou contido, insensível a maiúsculas)
            item_text_clean = item_text.strip().lower()
            # Tenta exato primeiro
            item = db.query(ListItem).filter(
                ListItem.list_id == lst.id,
                ListItem.done == False,
                func.lower(ListItem.text) == item_text_clean
            ).order_by(ListItem.id.desc()).first()
            if not item:
                # Tenta contido
                item = db.query(ListItem).filter(
                    ListItem.list_id == lst.id,
                    ListItem.done == False,
                    func.lower(ListItem.text).contains(item_text_clean)
                ).order_by(ListItem.id.desc()).first()

        if not item:
            from backend.locale import LIST_ITEM_NOT_FOUND
            return LIST_ITEM_NOT_FOUND.get(lang, LIST_ITEM_NOT_FOUND["en"]).format(item_id=item_id or item_text)

        item_id = item.id
        item_text = item.text
        item.done = True  # soft-delete
        payload = json.dumps({"list_name": list_name, "item_id": item_id, "item_text": item_text})
        db.add(AuditLog(user_id=user_id, action="list_remove", resource=f"{list_name}#{item_id}", payload_json=payload))
        db.commit()
        from backend.locale import LIST_ITEM_REMOVED
        return LIST_ITEM_REMOVED.get(lang, LIST_ITEM_REMOVED["en"]).format(item_id=item_id, list_name=list_name)

    def _delete_list(self, db, user_id: int, list_name: str) -> str:
        """Apaga a lista completa e todos os seus itens."""
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        lang = self._get_lang()
        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_DELETE
            return LIST_NAME_REQUIRED_DELETE.get(lang, LIST_NAME_REQUIRED_DELETE["en"])
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            from backend.locale import LIST_NOT_FOUND
            return LIST_NOT_FOUND.get(lang, LIST_NOT_FOUND["en"]).format(list_name=list_name)
        
        # Log before delete
        payload = json.dumps({"list_name": list_name, "item_count": len(lst.items)})
        db.add(AuditLog(user_id=user_id, action="list_delete_full", resource=list_name, payload_json=payload))
        
        # Hard delete (cascades to items via SQLAlchemy relationship)
        db.delete(lst)
        db.commit()
        from backend.locale import LIST_DELETED
        return LIST_DELETED.get(lang, LIST_DELETED["en"]).format(list_name=list_name)

    def _delete_all_lists(self, db, user_id: int) -> str:
        """Apaga ABSOLUTAMENTE TODAS as listas e itens do utilizador."""
        from backend.models_db import List, ListItem, AuditLog
        lang = self._get_lang()
        
        lists = db.query(List).filter(List.user_id == user_id).all()
        if not lists:
            from backend.locale import LIST_NO_LISTS
            return LIST_NO_LISTS.get(lang, LIST_NO_LISTS["en"])
        
        count = len(lists)
        for lst in lists:
            db.query(ListItem).filter(ListItem.list_id == lst.id).delete()
            db.delete(lst)
        
        db.add(AuditLog(user_id=user_id, action="list_delete_all", resource="all_lists", payload_json=json.dumps({"count": count})))
        db.commit()
        
        # Mensagem de sucesso (podemos adicionar ao locale.py depois, por agora usamos uma fixa ou reutilizamos)
        msgs = {
            "pt-PT": f"🛳️ *Todas as tuas {count} listas foram apagadas!* Tens agora uma folha em branco.",
            "pt-BR": f"🛳️ *Todas as suas {count} listas foram apagadas!* Você tem agora uma folha em branco.",
            "es": f"🛳️ *¡Todas tus {count} listas han sido borradas!* Ahora tienes una hoja en blanco.",
            "en": f"🛳️ *All your {count} lists have been deleted!* You now have a blank slate."
        }
        return msgs.get(lang, msgs["en"])

    def _resolve_list_by_item_id(self, db, user_id: int, item_id: int) -> str | None:
        """Encontra o nome da lista que contém o item com este id (do utilizador)."""
        item = db.query(ListItem).join(List).filter(List.user_id == user_id, ListItem.id == item_id).first()
        return item.list_ref.name if item and item.list_ref else None

    def _shuffle(self, db, user_id: int, list_name: str) -> str:
        """Embaralha a ordem dos itens na lista (in-place)."""
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        lang = self._get_lang()
        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_SHUFFLE
            return LIST_NAME_REQUIRED_SHUFFLE.get(lang, LIST_NAME_REQUIRED_SHUFFLE["en"])
        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            from backend.locale import LIST_NOT_FOUND
            return LIST_NOT_FOUND.get(lang, LIST_NOT_FOUND["en"]).format(list_name=list_name)
        items = (
            db.query(ListItem)
            .filter(ListItem.list_id == lst.id, ListItem.done == False)
            .order_by(ListItem.position, ListItem.id)
            .all()
        )
        if not items:
            from backend.locale import LIST_EMPTY
            return LIST_EMPTY.get(lang, LIST_EMPTY["en"]).format(list_name=list_name)
        if len(items) == 1:
            from backend.locale import LIST_ONLY_ONE_ITEM
            return LIST_ONLY_ONE_ITEM.get(lang, LIST_ONLY_ONE_ITEM["en"]).format(list_name=list_name)
        order = list(range(len(items)))
        random.shuffle(order)
        for i, item in enumerate(items):
            item.position = order[i]
        payload = json.dumps({"list_name": list_name, "item_count": len(items)})
        db.add(AuditLog(user_id=user_id, action="list_shuffle", resource=list_name, payload_json=payload))
        db.commit()
        from backend.locale import LIST_SHUFFLED
        return LIST_SHUFFLED.get(lang, LIST_SHUFFLED["en"]).format(list_name=list_name, count=len(items))

    def _feito(self, db, user_id: int, list_name: str, item_id: int | None = None, item_text: str | None = None) -> str:
        list_name = sanitize_string(list_name or "", MAX_LIST_NAME_LEN)
        lang = self._get_lang()
        if not list_name and item_id:
            list_name = self._resolve_list_by_item_id(db, user_id, item_id)

        if not list_name:
            from backend.locale import LIST_NAME_REQUIRED_FEITO
            return LIST_NAME_REQUIRED_FEITO.get(lang, LIST_NAME_REQUIRED_FEITO["en"])

        lst = db.query(List).filter(List.user_id == user_id, List.name == list_name).first()
        if not lst:
            from backend.locale import LIST_NOT_FOUND
            return LIST_NOT_FOUND.get(lang, LIST_NOT_FOUND["en"]).format(list_name=list_name)

        item = None
        if item_id is not None:
            item = db.query(ListItem).filter(ListItem.list_id == lst.id, ListItem.id == item_id).first()
        elif item_text:
            item_text_clean = item_text.strip().lower()
            item = db.query(ListItem).filter(
                ListItem.list_id == lst.id,
                ListItem.done == False,
                func.lower(ListItem.text) == item_text_clean
            ).order_by(ListItem.id.desc()).first()
            if not item:
                item = db.query(ListItem).filter(
                    ListItem.list_id == lst.id,
                    ListItem.done == False,
                    func.lower(ListItem.text).contains(item_text_clean)
                ).order_by(ListItem.id.desc()).first()

        if not item:
            from backend.locale import LIST_ITEM_NOT_FOUND
            return LIST_ITEM_NOT_FOUND.get(lang, LIST_ITEM_NOT_FOUND["en"]).format(item_id=item_id or item_text)

        item_id = item.id
        item_text = item.text
        item.done = True
        payload = json.dumps({"list_name": list_name, "item_id": item_id, "item_text": item_text})
        db.add(AuditLog(user_id=user_id, action="list_feito", resource=f"{list_name}#{item_id}", payload_json=payload))
        db.commit()
        from backend.locale import LIST_FEITO
        return LIST_FEITO.get(lang, LIST_FEITO["en"]).format(item_id=item_id, list_name=list_name)
