"""Sistema de bookmarks: /save, /bookmark, /find. Mimo para tags, categoria e busca semântica."""

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from backend.models_db import Bookmark
from backend.sanitize import sanitize_string, MAX_MESSAGE_LEN
from backend.user_store import get_or_create_user


def _parse_tags_and_category(out: str) -> tuple[list[str], str]:
    """Extrai tags e categoria da resposta do Mimo. Formato: TAGS: a, b, c | CATEGORIA: x"""
    tags: list[str] = []
    category = "outro"
    out = (out or "").strip()
    m_tags = re.search(r"TAGS?:\s*(.+?)(?:\s*\|\s*|$)", out, re.I | re.S)
    if m_tags:
        raw = m_tags.group(1).strip()
        tags = [t.strip() for t in re.split(r"[,;]", raw) if t.strip()][:10]
    m_cat = re.search(r"CATEGORIA:\s*(\w+)", out, re.I)
    if m_cat:
        cat = (m_cat.group(1) or "").strip().lower()
        if cat in ("receita", "ideia", "link", "tarefa", "lembrete", "outro"):
            category = cat
    return tags, category


async def generate_tags_and_category(
    mimo_provider: Any,
    mimo_model: str,
    content: str,
    context: str | None,
    user_lang: str = "pt-BR",
) -> tuple[list[str], str]:
    """
    Mimo: extrai tags e categoria do conteúdo. Retorna (tags, category).
    """
    if not mimo_provider or not mimo_model or not content or not content.strip():
        return [], "outro"
    ctx = f"\nContexto (mensagem anterior do assistente): {context[:200]}" if context else ""
    lang_inst = {
        "pt-PT": "português de Portugal",
        "pt-BR": "português do Brasil",
        "es": "espanhol",
        "en": "inglês",
    }.get(user_lang, "português")
    prompt = f"""Analisa este conteúdo guardado pelo utilizador e extrai:
1. TAGS: 3 a 6 palavras-chave separadas por vírgula (ex: receita, lasanha, espinafres)
2. CATEGORIA: uma destas — receita | ideia | link | tarefa | lembrete | outro

Conteúdo: «{content[:400]}»{ctx}

Responde APENAS com este formato, em {lang_inst}:
TAGS: palavra1, palavra2, palavra3
CATEGORIA: categoria"""
    try:
        r = await mimo_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=mimo_model,
            max_tokens=120,
            temperature=0,
        )
        return _parse_tags_and_category(r.content or "")
    except Exception:
        return [], "outro"


async def find_matching_bookmarks(
    mimo_provider: Any,
    mimo_model: str,
    query: str,
    bookmarks: list[dict],
    user_lang: str = "pt-BR",
) -> list[int]:
    """
    Mimo: dado query "aquela receita" e lista de bookmarks, retorna IDs dos que fazem match.
    bookmarks: [{"id": 1, "content": "...", "tags": "a,b,c", "category": "..."}, ...]
    """
    if not mimo_provider or not mimo_model or not query or not query.strip():
        return [b["id"] for b in bookmarks[:5]]  # fallback: primeiros
    if not bookmarks:
        return []
    bk_list = "\n".join(
        f"ID={b['id']} | {b['content'][:80]}... | tags:{b.get('tags','')} | cat:{b.get('category','')}"
        for b in bookmarks[:25]
    )
    lang_inst = {"pt-PT": "português", "pt-BR": "português", "es": "espanhol", "en": "inglês"}.get(user_lang, "português")
    prompt = f"""O utilizador procura com a query: «{query[:150]}»

Estes são os bookmarks (ID, conteúdo, tags, categoria):
{bk_list}

Quais IDs fazem match com a query? O utilizador pode usar linguagem vaga ("aquela receita", "o que guardei da avó").
Responde APENAS com os IDs separados por vírgula (ex: 1, 3, 5). Se nenhum fizer match: 0"""
    try:
        r = await mimo_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            model=mimo_model,
            max_tokens=80,
            temperature=0,
        )
        out = (r.content or "").strip()
        ids: list[int] = []
        for part in re.split(r"[,;\s]+", out):
            part = part.strip()
            if part.isdigit():
                n = int(part)
                if n > 0 and any(b["id"] == n for b in bookmarks):
                    ids.append(n)
        return ids[:10]
    except Exception:
        return []


def save_bookmark(
    db: Session,
    user_id: int,
    content: str,
    context: str | None,
    tags: list[str],
    category: str,
) -> Bookmark:
    """Persiste um bookmark."""
    content_clean = sanitize_string(content or "", MAX_MESSAGE_LEN)
    if not content_clean:
        raise ValueError("Conteúdo vazio")
    tags_json = json.dumps(tags[:15] if tags else [])
    b = Bookmark(
        user_id=user_id,
        content=content_clean,
        context=(context or "")[:500] if context else None,
        tags_json=tags_json,
        category=(category or "outro")[:32],
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def list_bookmarks(db: Session, user_id: int, limit: int = 30) -> list[Bookmark]:
    """Lista bookmarks do utilizador, mais recentes primeiro."""
    return (
        db.query(Bookmark)
        .filter(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc())
        .limit(limit)
        .all()
    )
