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


def _redirect_to_test_db(url: str) -> str:
    parts = url.rsplit("/", 1)
    if len(parts) == 2:
        db_and_query = parts[1]
        if "?" in db_and_query:
            db_name, query = db_and_query.split("?", 1)
            if db_name == "postgres":
                db_name = "healthai_test"
            parts[1] = f"{db_name}?{query}"
        else:
            if db_and_query == "postgres":
                parts[1] = "healthai_test"
        return "/".join(parts)
    return url


# If running in test mode, set a fallback or redirect to test database on Supabase
is_testing = os.getenv("TESTING") in ("True", "true")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL and is_testing:
    # Safe fallback if run without env file in local test environment
    DATABASE_URL = "sqlite:///:memory:"

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is missing. Supabase connection required.")

DATABASE_URL = _normalize_db_url(DATABASE_URL)

if is_testing and "sqlite" not in DATABASE_URL:
    DATABASE_URL = _redirect_to_test_db(DATABASE_URL)

# Direct connection (Supabase port 5432) — use for DDL/migrations when pooler is configured
DIRECT_DATABASE_URL = os.getenv("DIRECT_DATABASE_URL")
if DIRECT_DATABASE_URL:
    DIRECT_DATABASE_URL = _normalize_db_url(DIRECT_DATABASE_URL)
    if is_testing and "sqlite" not in DIRECT_DATABASE_URL:
        DIRECT_DATABASE_URL = _redirect_to_test_db(DIRECT_DATABASE_URL)


def _build_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(
        url,
        connect_args={"connect_timeout": 15},
        pool_pre_ping=True,
    )


# Runtime engine (pooler / app traffic)
# For testing mode, we prefer the direct connection to avoid pooler transaction lock issues during DDL/seeding/teardown!
test_engine_url = DIRECT_DATABASE_URL if (is_testing and DIRECT_DATABASE_URL) else DATABASE_URL
engine = _build_engine(test_engine_url)


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
