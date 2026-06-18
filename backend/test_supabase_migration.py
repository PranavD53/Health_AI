import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

# Load env before importing database components
load_dotenv()

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app import models

def main():
    print("Connecting to database...")
    db_url = os.getenv("DATABASE_URL", "")
    print(f"DATABASE_URL: {db_url[:40]}...")
    
    try:
        # Check connection
        with engine.connect() as conn:
            print("Successfully connected to Supabase database!")
            
            # Verify and count table records
            for table in ["users", "doctors", "doctor_verifications", "patient_profiles", "appointments", "symptom_logs"]:
                try:
                    res = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = res.scalar()
                    print(f"Table '{table}' exists: count = {count}")
                except Exception as e:
                    print(f"Table '{table}' does not exist or failed: {e}")
                    
            # Let's check user columns
            try:
                res = conn.execute(text("SELECT id, email, role, is_active, admin_requested FROM users LIMIT 1"))
                row = res.fetchone()
                print(f"User table columns check: {row}")
            except Exception as e:
                print(f"Failed to query User columns: {e}")
                
            # Let's run migrations manually to make sure
            print("Ensuring all columns exist...")
            migrations = [
                ("users", "otp", "VARCHAR"),
                ("users", "is_verified", "BOOLEAN DEFAULT FALSE"),
                ("users", "admin_requested", "BOOLEAN DEFAULT FALSE"),
                ("patient_profiles", "address", "TEXT"),
                ("patient_profiles", "profile_picture", "VARCHAR"),
                ("doctors", "address", "TEXT"),
                ("doctors", "profile_picture", "VARCHAR"),
                ("doctors", "license_document_path", "VARCHAR"),
                ("doctors", "license_number", "VARCHAR"),
                ("doctors", "user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
            ]
            
            for table, col, col_type in migrations:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                    print(f"Executed: ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type};")
                except Exception as e:
                    print(f"Error adding {col} to {table}: {e}")
            
    except Exception as e:
        print(f"Database connection failed: {e}")

if __name__ == "__main__":
    main()
