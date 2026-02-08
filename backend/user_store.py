"""User lookup by phone: get_or_create with truncated PII, hash for id."""

import hashlib
from sqlalchemy.orm import Session

from backend.models_db import User, _truncate_phone


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
