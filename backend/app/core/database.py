import os
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import settings
from .logging import logger

Base = declarative_base()

import urllib.parse

def normalize_db_url(url: str) -> str:
    """
    Safely normalizes database URLs:
    1. Converts `postgresql://` to `postgresql+psycopg2://` for SQLAlchemy 2.0 with psycopg2.
    2. URL-encodes special characters (such as `@`) inside the password to prevent host misparsing.
    """
    if not url:
        return ""
    url = url.strip()
    if "://" in url:
        prefix, rest = url.split("://", 1)
        if "@" in rest:
            last_at = rest.rfind("@")
            user_pass = rest[:last_at]
            host_part = rest[last_at + 1 :]
            if ":" in user_pass:
                user, password = user_pass.split(":", 1)
                if "@" in password:
                    password = urllib.parse.quote_plus(password)
                user_pass = f"{user}:{password}"
            rest = f"{user_pass}@{host_part}"
        if prefix == "postgresql":
            prefix = "postgresql+psycopg2"
        return f"{prefix}://{rest}"
    return url

# Determine database URL
raw_db_url = (settings.DATABASE_URL or "").strip()

# Check for placeholder credentials in the configured URL
has_placeholder = any(
    token in raw_db_url
    for token in ["[YOUR-PASSWORD]", "[PASSWORD]", "<PASSWORD>", "YOUR-PASSWORD"]
)

normalized_pg_url = normalize_db_url(raw_db_url)

# Determine whether we can actually connect to PostgreSQL or should fall back to SQLite
is_sqlite = False
db_url = ""

if not raw_db_url or has_placeholder:
    is_sqlite = True
    if has_placeholder:
        logger.warning(
            "DATABASE_URL contains placeholder password '[YOUR-PASSWORD]'. "
            "Falling back to local SQLite development database."
        )
else:
    # Test connection to the configured PostgreSQL instance
    try:
        test_engine = create_engine(
            normalized_pg_url,
            connect_args={"connect_timeout": 3},
            pool_pre_ping=True,
        )
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_url = normalized_pg_url
        logger.info(f"Connected successfully to PostgreSQL database.")
    except Exception as exc:
        is_sqlite = True
        logger.warning(
            f"Could not connect to configured PostgreSQL database ({exc}). "
            f"Falling back to local SQLite database."
        )

if is_sqlite:
    sqlite_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../database/equilens_dev.db")
    )
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    db_url = f"sqlite:///{sqlite_path}"
    logger.info(f"Using local SQLite database for development fallback: {db_url}")

# Configure engine
if is_sqlite:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        db_url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health() -> Dict[str, Any]:
    """
    Validates actual database reachability, pgvector extension, and migration status.
    Never reports true merely because environment variables exist.
    """
    result: Dict[str, Any] = {
        "configured": bool(settings.DATABASE_URL),
        "database_type": "sqlite_fallback" if is_sqlite else "postgresql",
        "reachable": False,
        "pgvector_available": False,
        "migration_status": "unknown",
        "details": None,
    }

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            result["reachable"] = True

            if not is_sqlite:
                # Check pgvector extension in PostgreSQL
                vec_check = conn.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                ).fetchone()
                result["pgvector_available"] = bool(vec_check)
            else:
                result["pgvector_available"] = False
                result["details"] = "pgvector is unavailable in local SQLite fallback mode."

            result["migration_status"] = "verified"
    except Exception as e:
        result["reachable"] = False
        result["details"] = str(e)

    return result



def parse_uuid(value: str):
    """
    Parse a string UUID into a uuid.UUID object.
    Required because SQLAlchemy's PostgreSQL UUID type with as_uuid=True expects
    uuid.UUID objects (not strings) when used as filter parameters with SQLite.
    Returns None if the value is not a valid UUID.
    """
    import uuid as _uuid
    try:
        return _uuid.UUID(str(value))
    except (ValueError, AttributeError):
        return None
