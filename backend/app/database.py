import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from dotenv import load_dotenv

# Load .env file relative to this file
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

def _normalize_db_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is missing. Supabase connection required.")

DATABASE_URL = _normalize_db_url(DATABASE_URL)

# Direct connection (Supabase port 5432) — use for DDL/migrations when pooler is configured
DIRECT_DATABASE_URL = os.getenv("DIRECT_DATABASE_URL")
if DIRECT_DATABASE_URL:
    DIRECT_DATABASE_URL = _normalize_db_url(DIRECT_DATABASE_URL)


def _build_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        connect_args={"connect_timeout": 15},
        pool_pre_ping=True,
    )


# Runtime engine (pooler / app traffic)
engine = _build_engine(DATABASE_URL)


def get_migration_engine():
    """Engine for schema changes — prefers direct Postgres URL over transaction pooler."""
    migration_url = DIRECT_DATABASE_URL or DATABASE_URL
    if migration_url == DATABASE_URL:
        return engine
    return _build_engine(migration_url)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
