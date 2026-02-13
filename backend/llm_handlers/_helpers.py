"""Helpers usados pelos handlers LLM."""

def get_user_lang(chat_id: str) -> str:
    """Obtém idioma do utilizador. Fallback: en."""
    try:
        from backend.database import SessionLocal
        from backend.user_store import get_user_language
        db = SessionLocal()
        try:
            return get_user_language(db, chat_id) or "en"
        finally:
            db.close()
    except Exception:
        return "en"
