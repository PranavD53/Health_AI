import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

# Configure test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_12345"
os.environ["LIVEKIT_API_KEY"] = "test_lk_key"
os.environ["LIVEKIT_API_SECRET"] = "test_lk_secret"
os.environ["LIVEKIT_URL"] = "wss://test.livekit.cloud"

from app.main import app
from app.database import Base, get_db
from app import models

# Create memory database engine
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def setup_module():
    Base.metadata.create_all(bind=engine)
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
    Base.metadata.drop_all(bind=engine)
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
        assert "token" in data
        assert data["sfu_url"] == "wss://test.livekit.cloud"
        call_id = data["call_id"]

        # Decode and verify the Doctor token claims
        decoded_doc = jwt.decode(data["token"], "test_lk_secret", algorithms=["HS256"])
        assert decoded_doc["iss"] == "test_lk_key"
        assert decoded_doc["video"]["room"].startswith(f"room_app_{appointment_id}")
        assert decoded_doc["video"]["roomJoin"] is True
        assert decoded_doc["video"]["canPublish"] is True

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
        assert "token" in accept_data
        assert accept_data["sfu_url"] == "wss://test.livekit.cloud"

        # Decode and verify Patient token claims
        decoded_pat = jwt.decode(accept_data["token"], "test_lk_secret", algorithms=["HS256"])
        assert decoded_pat["iss"] == "test_lk_key"
        assert decoded_pat["video"]["room"].startswith(f"room_app_{appointment_id}")
        assert decoded_pat["video"]["canPublish"] is True

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
