"""SQLite database session and init. PII: phone stored truncated (e.g. 55119***9999)."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.models_db import Base

# Default: ~/.nanobot/organizer.db
DATA_DIR = Path.home() / ".nanobot"
DB_PATH = DATA_DIR / "organizer.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)

ENGINE = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def init_db() -> None:
    """Create tables if not exist. Add missing columns for existing DBs (e.g. users.language)."""
    Base.metadata.create_all(bind=ENGINE)
    for col_sql in (
        "ALTER TABLE users ADD COLUMN preferred_name VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN language VARCHAR(8)",
        "ALTER TABLE users ADD COLUMN timezone VARCHAR(64)",
    ):
        try:
            from sqlalchemy import text
            with ENGINE.connect() as conn:
                conn.execute(text(col_sql))
                conn.commit()
        except Exception:
            pass  # Coluna já existe ou tabela não existe


def get_db():
    """Dependency for FastAPI (yields Session)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
