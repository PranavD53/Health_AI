import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = "test_secret_key_12345"

from app.database import engine, Base, SessionLocal
from app.main import seed_demo_users
from app.routes.doctors import seed_doctors
from test_api import _cleanup_db

Base.metadata.create_all(bind=engine)
_cleanup_db(engine, Base)
db = SessionLocal()
try:
    print("Seeding doctors...")
    seed_doctors(db)
    print("Seeding demo users...")
    seed_demo_users(db)
    print("Success!")
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.close()
