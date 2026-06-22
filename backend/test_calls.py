import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

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
    # Override cached module-level constants in calls.py
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

def test_video_calls_flow():
    setup_module()
    try:
        # 1. Register & Login Doctor and Patient with fresh profiles
        patient_reg = client.post("/auth/register", json={
            "email": "test_call_patient@example.com",
            "password": "patientpassword",
            "role": "patient"
        })
        assert patient_reg.status_code == 201, patient_reg.text
        patient_id = patient_reg.json()["id"]
        
        patient_login = client.post("/auth/login", json={
            "email": "test_call_patient@example.com",
            "password": "patientpassword"
        })
        assert patient_login.status_code == 200, patient_login.text
        patient_headers = {"Authorization": f"Bearer {patient_login.json()['access_token']}"}

        doctor_reg = client.post("/auth/register", json={
            "email": "test_call_doctor@example.com",
            "password": "doctorpassword",
            "role": "doctor"
        })
        assert doctor_reg.status_code == 201, doctor_reg.text
        doctor_user_id = doctor_reg.json()["id"]
        
        doctor_login = client.post("/auth/login", json={
            "email": "test_call_doctor@example.com",
            "password": "doctorpassword"
        })
        assert doctor_login.status_code == 200, doctor_login.text
        doctor_headers = {"Authorization": f"Bearer {doctor_login.json()['access_token']}"}
        
        db = TestingSessionLocal()
        try:
            # We insert a new doctor profile associated with doctor_user_id
            doctor_profile = models.Doctor(
                user_id=doctor_user_id,
                name="Dr. Testing LiveKit",
                specialization="General Telemedicine",
                location="Virtual Clinic Room 1",
                experience_years=5,
                available=True,
                contact="test_call_doctor@example.com",
                license_number="MD-TEST-999"
            )
            db.add(doctor_profile)
            db.commit()
            db.refresh(doctor_profile)
            doc_id = doctor_profile.id
            
            # Create a mock appointment
            appointment = models.Appointment(
                patient_id=patient_id,
                doctor_id=doc_id,
                date="2026-06-25",
                time="10:30",
                status="booked"
            )
            db.add(appointment)
            db.commit()
            db.refresh(appointment)
            appointment_id = appointment.id
        finally:
            db.close()

        # 2. Test Call Initiation by Doctor
        print("Testing Call Initiation...")
        init_resp = client.post(
            "/calls/initiate",
            headers=doctor_headers,
            json={"appointment_id": appointment_id}
        )
        assert init_resp.status_code == 200, init_resp.text
        data = init_resp.json()
        assert "call_id" in data
        assert data["room_id"].startswith(f"room_app_{appointment_id}")
        assert data["peer_id"] == patient_id
        assert data["token"] is None
        assert data["sfu_url"] is None
        call_id = data["call_id"]

        # Verify that CallRecord is stored as INITIATED in DB
        db = TestingSessionLocal()
        try:
            call_rec = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
            assert call_rec is not None
            assert call_rec.status == "INITIATED"
            assert call_rec.appointment_id == appointment_id
            assert call_rec.patient_id == patient_id
        finally:
            db.close()

        # 3. Test Call Acceptance by Patient
        print("Testing Call Acceptance...")
        accept_resp = client.post(
            f"/calls/{call_id}/accept",
            headers=patient_headers
        )
        assert accept_resp.status_code == 200, accept_resp.text
        accept_data = accept_resp.json()
        assert accept_data["call_id"] == call_id
        assert accept_data["peer_id"] == doctor_user_id
        assert accept_data["token"] is None
        assert accept_data["sfu_url"] is None


        # Verify call status changed to ACCEPTED in DB
        db = TestingSessionLocal()
        try:
            call_rec = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
            assert call_rec.status == "ACCEPTED"
            assert call_rec.accepted_at is not None
        finally:
            db.close()

        # 4. Test Call Termination
        print("Testing Call Termination...")
        end_resp = client.post(
            f"/calls/{call_id}/end",
            headers=doctor_headers
        )
        assert end_resp.status_code == 200, end_resp.text
        end_data = end_resp.json()
        assert end_data["call_id"] == call_id
        assert end_data["status"] == "COMPLETED"
        assert end_data["duration_seconds"] >= 0

        # Verify database CallRecord details
        db = TestingSessionLocal()
        try:
            call_rec = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
            assert call_rec.status == "COMPLETED"
            assert call_rec.ended_at is not None
            
            # Verify AuditLog entries
            audits = db.query(models.VideoCallAuditLog).filter(models.VideoCallAuditLog.call_id == call_id).all()
            assert len(audits) >= 3  # INITIATE, ACCEPT, END
            actions = [a.action for a in audits]
            assert "INITIATE_CALL" in actions
            assert "ACCEPT_CALL" in actions
            assert "END_CALL" in actions
        finally:
            db.close()

        # 5. Verify Unauthorized and Invalid Requests
        print("Testing Call Authorization constraints...")
        # Patients cannot initiate calls
        unauth_init = client.post(
            "/calls/initiate",
            headers=patient_headers,
            json={"appointment_id": appointment_id}
        )
        assert unauth_init.status_code == 403

        # Doctors cannot accept calls meant for patient
        unauth_accept = client.post(
            f"/calls/{call_id}/accept",
            headers=doctor_headers
        )
        assert unauth_accept.status_code == 403

        print("\n=== VIDEO CALLS INTEGRATION TESTS PASSED SUCCESSFULLY ===")

    finally:
        teardown_module()

if __name__ == "__main__":
    test_video_calls_flow()
