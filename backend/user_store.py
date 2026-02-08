"""User lookup by phone: get_or_create with truncated PII, hash for id. Idioma por chat_id."""

import hashlib
from sqlalchemy.orm import Session

from backend.models_db import User, _truncate_phone
from backend.locale import LangCode, phone_to_default_language


def phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def get_or_create_user(db: Session, phone: str) -> User:
    h = phone_hash(phone)
    user = db.query(User).filter(User.phone_hash == h).first()
    if user:
        return user
    user = User(
        phone_hash=h,
        phone_truncated=_truncate_phone(phone),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_language(db: Session, chat_id: str) -> LangCode:
    """Idioma do utilizador: guardado ou inferido pelo prefixo do número (pt-BR, pt-PT, es, en)."""
    from backend.locale import SUPPORTED_LANGS
    user = get_or_create_user(db, chat_id)
    if user.language and user.language in SUPPORTED_LANGS:
        return user.language  # type: ignore
    return phone_to_default_language(chat_id)


def set_user_language(db: Session, chat_id: str, lang: LangCode) -> None:
    """Grava preferência de idioma do utilizador (pt-PT, pt-BR, es, en)."""
    from backend.locale import SUPPORTED_LANGS
    if lang not in SUPPORTED_LANGS:
        return
    user = get_or_create_user(db, chat_id)
    user.language = lang
    db.commit()
