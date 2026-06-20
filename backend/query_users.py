import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

# Load env before importing database components relative to this file
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app import models

def main():
    db = SessionLocal()
    try:
        users = db.query(models.User).all()
        print(f"Total users: {len(users)}")
        print(f"{'ID':<5} | {'Email':<30} | {'Role':<10} | {'Active':<8} | {'Verified':<8} | {'AdminReq':<8}")
        print("-" * 80)
        for u in users:
            print(f"{u.id:<5} | {u.email:<30} | {u.role:<10} | {str(u.is_active):<8} | {str(u.is_verified):<8} | {str(u.admin_requested):<8}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
