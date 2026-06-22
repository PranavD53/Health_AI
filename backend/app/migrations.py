"""
Database schema bootstrap and incremental column migrations.

Order matters:
  1. create_all() — creates any missing tables from SQLAlchemy models
  2. column migrations — adds columns that were introduced after initial deploys
"""
import os
from sqlalchemy import inspect, text

from app.database import Base, get_migration_engine
from app import models  # noqa: F401 — register all models on Base.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def _table_exists(conn, table_name: str) -> bool:
    if _is_sqlite(str(conn.engine.url)):
        row = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name = :t"),
            {"t": table_name},
        ).fetchone()
        return row is not None

    return bool(
        conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables "
                "  WHERE table_schema = 'public' AND table_name = :t"
                ")"
            ),
            {"t": table_name},
        ).scalar()
    )


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    if _is_sqlite(str(conn.engine.url)):
        rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        return any(row[1] == column_name for row in rows)

    return bool(
        conn.execute(
            text(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns "
                "  WHERE table_schema = 'public' AND table_name = :t AND column_name = :c"
                ")"
            ),
            {"t": table_name, "c": column_name},
        ).scalar()
    )


def _column_migrations(db_url: str) -> list[tuple[str, str, str]]:
    is_sqlite = _is_sqlite(db_url)
    user_id_type = "INTEGER" if is_sqlite else "INTEGER REFERENCES users(id) ON DELETE SET NULL"

    return [
        # users
        ("users", "otp", "VARCHAR"),
        ("users", "is_verified", "BOOLEAN DEFAULT FALSE"),
        ("users", "admin_requested", "BOOLEAN DEFAULT FALSE"),
        ("users", "has_admin_permission", "BOOLEAN DEFAULT FALSE"),
        ("users", "base_role", "VARCHAR DEFAULT 'patient'"),
        # patient_profiles
        ("patient_profiles", "address", "TEXT"),
        ("patient_profiles", "profile_picture", "VARCHAR"),
        ("patient_profiles", "latitude", "FLOAT"),
        ("patient_profiles", "longitude", "FLOAT"),
        # doctors
        ("doctors", "address", "TEXT"),
        ("doctors", "profile_picture", "VARCHAR"),
        ("doctors", "profile_picture_data", "TEXT"),
        ("doctors", "license_document_path", "VARCHAR"),
        ("doctors", "license_document_data", "TEXT"),
        ("doctors", "license_number", "VARCHAR"),
        ("doctors", "user_id", user_id_type),
        # medical_records
        ("medical_records", "fraud_status", "VARCHAR DEFAULT 'VERIFIED (Authentic)'"),
        ("medical_records", "file_data", "TEXT"),
        # private chat (added after initial release)
        ("private_messages", "attachment_path", "VARCHAR"),
        ("private_messages", "attachment_name", "VARCHAR"),
        # appointments
        ("appointments", "priority", "VARCHAR DEFAULT 'Normal'"),
        # emergency alerts coordinates
        ("emergency_alerts", "latitude", "FLOAT"),
        ("emergency_alerts", "longitude", "FLOAT"),
        # doctors coordinates
        ("doctors", "latitude", "FLOAT"),
        ("doctors", "longitude", "FLOAT"),
    ]


def run_column_migrations(engine, db_url: str) -> dict:
    """Apply incremental ALTER TABLE migrations. Returns a summary dict."""
    summary = {"applied": [], "skipped": [], "failed": []}
    migrations = _column_migrations(db_url)
    is_sqlite = _is_sqlite(db_url)

    print("Running column migrations...")
    for table, col, col_type in migrations:
        try:
            with engine.begin() as conn:
                if not _table_exists(conn, table):
                    summary["skipped"].append(f"{table}.{col} (table missing — will be created by models)")
                    print(f"  skip {table}.{col}: table does not exist yet")
                    continue

                if _column_exists(conn, table, col):
                    summary["skipped"].append(f"{table}.{col} (already exists)")
                    continue

                if is_sqlite:
                    sql = f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"
                else:
                    sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type}"

                conn.execute(text(sql))
                summary["applied"].append(f"{table}.{col}")
                print(f"  applied {table}.{col}")
        except Exception as exc:
            summary["failed"].append(f"{table}.{col}: {exc}")
            print(f"  FAILED {table}.{col}: {exc}")

    return summary


def create_tables(engine) -> list[str]:
    """Create all tables defined in models that do not yet exist."""
    print("Creating missing tables from models...")
    before = set(inspect(engine).get_table_names())
    Base.metadata.create_all(bind=engine)
    after = set(inspect(engine).get_table_names())
    created = sorted(after - before)
    if created:
        for name in created:
            print(f"  created table: {name}")
    else:
        print("  all model tables already exist")
    return created


def ensure_schema(engine=None, db_url: str | None = None) -> dict:
    """
    Full schema sync: create missing tables, then apply column migrations.
    Safe to run on every startup or via `python migrate.py`.
    """
    engine = engine or get_migration_engine()
    db_url = db_url or os.getenv("DIRECT_DATABASE_URL") or os.getenv("DATABASE_URL", "")

    if not db_url:
        raise RuntimeError("DATABASE_URL is not configured")

    print(f"Using database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    created = create_tables(engine)
    column_summary = run_column_migrations(engine, db_url)

    # Seed clinical guidelines
    try:
        from sqlalchemy.orm import Session
        with Session(engine) as session:
            from app.seed_guidelines import seed_clinical_guidelines
            seed_clinical_guidelines(session)
    except Exception as seed_err:
        print(f"  WARNING: Seeding clinical guidelines failed: {seed_err}")

    # If running on PostgreSQL (not SQLite), run specific DDL for user_color_palettes (RLS, indexes)
    is_sqlite = _is_sqlite(db_url)
    if not is_sqlite:
        print("Running PostgreSQL specific migrations for user_color_palettes...")
        try:
            migration_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "migrations",
                "create_user_color_palettes.sql"
            )
            if os.path.exists(migration_file):
                with open(migration_file, "r") as f:
                    sql_content = f.read()
                
                # Execute the raw SQL script
                with engine.begin() as conn:
                    conn.execute(text(sql_content))
                print("  PostgreSQL specific migrations completed successfully.")
            else:
                print(f"  Migration file not found at {migration_file}")
        except Exception as e:
            print(f"  FAILED to run PostgreSQL specific migrations: {e}")

    result = {
        "tables_created": created,
        **column_summary,
    }

    if column_summary["failed"]:
        print(f"\nMigration completed with {len(column_summary['failed'])} error(s).")
    else:
        print("\nMigration completed successfully.")

    return result
