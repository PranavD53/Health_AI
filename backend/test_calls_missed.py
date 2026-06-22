import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test_secret_key_12345")
os.environ["LIVEKIT_API_KEY"] = os.environ.get("LIVEKIT_API_KEY", "test_lk_key")
os.environ["LIVEKIT_API_SECRET"] = os.environ.get("LIVEKIT_API_SECRET", "test_lk_secret")
os.environ["LIVEKIT_URL"] = os.environ.get("LIVEKIT_URL", "wss://test.livekit.cloud")

from app.main import app
from app.database import Base, get_db, engine, SessionLocal as TestingSessionLocal
from app import models

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def _cleanup_db(engine, Base):
    from sqlalchemy.orm import close_all_sessions
    try:
        close_all_sessions()
    except Exception:
        pass
    if "sqlite" in str(engine.url):
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception:
            pass
    else:
        from sqlalchemy import text
        tables = [t.name for t in Base.metadata.sorted_tables]
        if tables:
            tables_str = ", ".join(f'"{t}"' for t in tables)
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"))
            except Exception as e:
                print(f"Cleanup truncate skipped: {e}")


def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    from app.routes import calls
    calls.LIVEKIT_API_KEY = "test_lk_key"
    calls.LIVEKIT_API_SECRET = "test_lk_secret"
    calls.LIVEKIT_URL = "wss://test.livekit.cloud"
    
    Base.metadata.create_all(bind=engine)
    _cleanup_db(engine, Base)
    db = TestingSessionLocal()
    try:
        from app.routes.doctors import seed_doctors
        from app.main import seed_demo_users
        seed_doctors(db)
        seed_demo_users(db)
    finally:
        db.close()

def teardown_module():
    global engine
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
    _cleanup_db(engine, Base)
    engine.dispose()

def test_missed_call_flow():
    setup_module()
    try:
        # Register and login patient and doctor
        patient_reg = client.post("/auth/register", json={
            "email": "patient_missed@example.com",
            "password": "patientpassword",
            "role": "patient"
        })
        patient_id = patient_reg.json()["id"]
        
        patient_login = client.post("/auth/login", json={
            "email": "patient_missed@example.com",
            "password": "patientpassword"
        })
        
        doctor_reg = client.post("/auth/register", json={
            "email": "doctor_missed@example.com",
            "password": "doctorpassword",
            "role": "doctor"
        })
        doctor_user_id = doctor_reg.json()["id"]
        
        doctor_login = client.post("/auth/login", json={
            "email": "doctor_missed@example.com",
            "password": "doctorpassword"
        })
        doctor_headers = {"Authorization": f"Bearer {doctor_login.json()['access_token']}"}

        db = TestingSessionLocal()
        try:
            doctor_profile = models.Doctor(
                user_id=doctor_user_id,
                name="Dr. Missed Call",
                specialization="General",
                location="Virtual",
                experience_years=5,
                available=True,
                contact="doctor_missed@example.com",
                license_number="MD-MISSED-123"
            )
            db.add(doctor_profile)
            db.commit()
            db.refresh(doctor_profile)
            
            appointment = models.Appointment(
                patient_id=patient_id,
                doctor_id=doctor_profile.id,
                date="2026-06-25",
                time="11:30",
                status="booked"
            )
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            appointment_id = appointment.id
        finally:
            db.close()

        # Doctor initiates call
        init_resp = client.post(
            "/calls/initiate",
            headers=doctor_headers,
            json={"appointment_id": appointment_id}
        )
        assert init_resp.status_code == 200
        call_id = init_resp.json()["call_id"]

        # Check call is INITIATED
        db = TestingSessionLocal()
        try:
            call_rec = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
            assert call_rec.status == "INITIATED"
        finally:
            db.close()

        # Doctor ends call before patient accepts
        end_resp = client.post(
            f"/calls/{call_id}/end",
            headers=doctor_headers
        )
        assert end_resp.status_code == 200

        # Check call status is MISSED in DB
        db = TestingSessionLocal()
        try:
            call_rec = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
            assert call_rec.status == "MISSED"
        finally:
            db.close()
            
        print("\n=== MISSED CALL FLOW INTEGRATION TESTS PASSED SUCCESSFULLY ===")
    finally:
        teardown_module()

if __name__ == "__main__":
    test_missed_call_flow()
