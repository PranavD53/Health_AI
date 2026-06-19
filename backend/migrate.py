#!/usr/bin/env python
"""Run database migrations manually.

Usage (from backend/):
    python migrate.py

Requires DATABASE_URL in backend/.env
For Supabase, also set DIRECT_DATABASE_URL (port 5432) when using the pooler URL.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.migrations import ensure_schema


def main():
    try:
        result = ensure_schema()
        failed = result.get("failed", [])
        if failed:
            print("\nSome migrations failed:")
            for item in failed:
                print(f"  - {item}")
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:
        print(f"\nMigration failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
