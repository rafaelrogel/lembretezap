"""SQLite database session and init. PII: phone stored truncated (e.g. 55119***9999).

Produção: criptografia em repouso via SQLCipher (opcional) ou volume criptografado.
- Definir DB_PASSPHRASE para usar SQLCipher (requer pysqlcipher3 e libsqlcipher no sistema).
- Alternativa: montar volume criptografado (LUKS, BitLocker) e colocar o ficheiro da BD nesse volume.
"""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from backend.models_db import Base

# Caminho da BD:
#   DB_PATH (env) → caminho explícito
#   ZAPISTA_DATA (env) → diretório de dados (default ~/.zapista)
#   Default: ~/.zapista/organizer.db
#
# Múltiplos ambientes: Local usa ~/.zapista; Docker usa /root/.zapista (volume). São BDs diferentes
# salvo se montares o mesmo diretório. Para ter dados partilhados, usa DB_PATH apontando ao mesmo
# ficheiro ou NFS/volume partilhado.
_DATA_DIR = Path(os.environ.get("ZAPISTA_DATA", "").strip() or str(Path.home() / ".zapista"))
DB_PATH = Path(os.environ.get("DB_PATH", "").strip()) if os.environ.get("DB_PATH") else (_DATA_DIR / "organizer.db")
DATA_DIR = DB_PATH.parent
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Passphrase para SQLCipher (opcional). Se definido e pysqlcipher3 disponível, a BD fica criptografada.
_DB_PASSPHRASE = os.environ.get("DB_PASSPHRASE", "").strip() or None


def _make_engine():
    """Cria o engine: SQLCipher se DB_PASSPHRASE e pysqlcipher3; senão SQLite normal."""
    url = f"sqlite:///{DB_PATH}"
    connect_args: dict = {"check_same_thread": False}

    if _DB_PASSPHRASE:
        try:
            import pysqlcipher3.dbapi2 as sqlite_cipher  # type: ignore
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "DB_PASSPHRASE definido mas pysqlcipher3 não instalado; a BD será SQLite sem criptografia. "
                "Para SQLCipher: pip install pysqlcipher3 e instalar libsqlcipher no sistema."
            )
            return create_engine(url, connect_args=connect_args, poolclass=StaticPool)

        engine = create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool,
            module=sqlite_cipher,
        )
        # Definir a chave em cada nova conexão (obrigatório antes de qualquer query)
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlcipher_key(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA key = ?", (_DB_PASSPHRASE,))
            cursor.close()

        return engine

    return create_engine(url, connect_args=connect_args, poolclass=StaticPool)


def _is_using_sqlcipher() -> bool:
    try:
        import pysqlcipher3.dbapi2  # noqa: F401
        return bool(_DB_PASSPHRASE)
    except ImportError:
        return False


ENGINE = _make_engine()
_using_sqlcipher = _DB_PASSPHRASE and _is_using_sqlcipher()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def init_db() -> None:
    """Create tables if not exist. Add missing columns for existing DBs (e.g. users.language)."""
    Base.metadata.create_all(bind=ENGINE)
    for col_sql in (
        "ALTER TABLE users ADD COLUMN preferred_name VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN city VARCHAR(128)",
        "ALTER TABLE users ADD COLUMN default_reminder_lead_seconds INTEGER",
        "ALTER TABLE users ADD COLUMN extra_reminder_leads TEXT",
        "ALTER TABLE users ADD COLUMN language VARCHAR(8)",
        "ALTER TABLE users ADD COLUMN timezone VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN quiet_start VARCHAR(5)",
        "ALTER TABLE users ADD COLUMN quiet_end VARCHAR(5)",
        "ALTER TABLE reminder_history ADD COLUMN job_id VARCHAR(64)",
        "ALTER TABLE reminder_history ADD COLUMN schedule_at DATETIME",
        "ALTER TABLE reminder_history ADD COLUMN channel VARCHAR(32)",
        "ALTER TABLE reminder_history ADD COLUMN recipient VARCHAR(256)",
        "ALTER TABLE reminder_history ADD COLUMN status VARCHAR(16)",
        "ALTER TABLE reminder_history ADD COLUMN delivered_at DATETIME",
        "ALTER TABLE reminder_history ADD COLUMN provider_error VARCHAR(256)",
        "ALTER TABLE lists ADD COLUMN project_id INTEGER",
        "ALTER TABLE audit_log ADD COLUMN payload_json TEXT",
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


def is_encrypted() -> bool:
    """True se a BD está a usar SQLCipher (DB_PASSPHRASE definido e pysqlcipher3 em uso)."""
    return _using_sqlcipher
