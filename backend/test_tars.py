import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Load env
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.services.tars_engine import execute_tars_intent

async def test_booking():
    db = SessionLocal()
    try:
        # Find a patient user
        user = db.query(models.User).filter(models.User.role == "patient").first()
        if not user:
            print("No patient user found!")
            return
        
        print(f"Testing for user: {user.email}, role: {user.role}")
        
        # Call tars engine
        res = await execute_tars_intent(
            message="Book a visit with Dr. Bharagav Nama at 5:00 PM on 2026-06-25",
            current_user=user,
            db=db,
            language="en"
        )
        print("Result:")
        print(res)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_booking())
