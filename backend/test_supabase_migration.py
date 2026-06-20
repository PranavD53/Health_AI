import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load env before database import
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text

from app.database import engine, get_migration_engine
from app.migrations import ensure_schema


def main():
    db_url = os.getenv("DATABASE_URL", "")
    print(f"DATABASE_URL host: {db_url.split('@')[-1] if '@' in db_url else '(not set)'}")

    direct = os.getenv("DIRECT_DATABASE_URL")
    if direct:
        print(f"DIRECT_DATABASE_URL host: {direct.split('@')[-1]}")
    else:
        print("DIRECT_DATABASE_URL: not set (using DATABASE_URL for migrations)")

    try:
        with engine.connect() as conn:
            print("Successfully connected to database.")
    except Exception as exc:
        print(f"Database connection failed: {exc}")
        sys.exit(1)

    result = ensure_schema(engine=get_migration_engine())

    print("\n--- Table row counts ---")
    tables = [
        "users", "doctors", "doctor_verifications", "patient_profiles",
        "appointments", "symptom_logs", "medical_records", "private_conversations",
        "private_messages", "notifications", "emergency_alerts", "complaints",
    ]
    with engine.connect() as conn:
        for table in tables:
            try:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                print(f"  {table}: {count} rows")
            except Exception as exc:
                print(f"  {table}: MISSING or error ({exc})")

    if result.get("failed"):
        sys.exit(1)


if __name__ == "__main__":
    main()
