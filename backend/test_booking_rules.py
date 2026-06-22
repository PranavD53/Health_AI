import os
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test_secret_key_12345")

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

def test_appointment_booking_rules_and_notifications():
    setup_module()
    try:
        # Register and login patient and doctor
        patient_reg = client.post("/auth/register", json={
            "email": "pat_booking@example.com",
            "password": "patientpassword",
            "role": "patient"
        })
        patient_id = patient_reg.json()["id"]
        
        patient_login = client.post("/auth/login", json={
            "email": "pat_booking@example.com",
            "password": "patientpassword"
        })
        patient_headers = {"Authorization": f"Bearer {patient_login.json()['access_token']}"}
        
        doctor_reg = client.post("/auth/register", json={
            "email": "doc_booking@example.com",
            "password": "doctorpassword",
            "role": "doctor"
        })
        doctor_user_id = doctor_reg.json()["id"]
        
        db = TestingSessionLocal()
        try:
            # Create Doctor Profile
            doctor_profile = models.Doctor(
                user_id=doctor_user_id,
                name="Dr. Booking Rules",
                specialization="General Telemedicine",
                location="Room 5",
                experience_years=8,
                available=True,
                contact="doc_booking@example.com",
                license_number="MD-RULES-555"
            )
            db.add(doctor_profile)
            db.commit()
            db.refresh(doctor_profile)
            doc_id = doctor_profile.id
        finally:
            db.close()

        today = datetime.date.today()

        # 1. Booking less than 2 days in advance (should fail with 400)
        tomorrow_str = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        resp_advance = client.post(
            "/appointment/book",
            headers=patient_headers,
            json={
                "doctor_id": doc_id,
                "date": tomorrow_str,
                "time": "10:00"
            }
        )
        assert resp_advance.status_code == 400
        assert "at least 2 days in advance" in resp_advance.json()["detail"]

        # 2. Booking with an unavailable doctor (should fail with 400)
        # Update doctor availability to False
        db = TestingSessionLocal()
        try:
            doc = db.query(models.Doctor).filter(models.Doctor.id == doc_id).first()
            doc.available = False
            db.commit()
        finally:
            db.close()

        future_str = (today + datetime.timedelta(days=3)).strftime("%Y-%m-%d")
        resp_unavailable = client.post(
            "/appointment/book",
            headers=patient_headers,
            json={
                "doctor_id": doc_id,
                "date": future_str,
                "time": "11:00"
            }
        )
        assert resp_unavailable.status_code == 400
        assert "unavailable" in resp_unavailable.json()["detail"].lower()

        # Check notification was created for doctor
        db = TestingSessionLocal()
        try:
            notif = db.query(models.Notification).filter(models.Notification.user_id == doctor_user_id).first()
            assert notif is not None
            assert "unavailable" in notif.message.lower()
            # Delete this notification to test next cases cleanly
            db.delete(notif)
            db.commit()
        finally:
            db.close()

        # Reset doctor availability to True
        db = TestingSessionLocal()
        try:
            doc = db.query(models.Doctor).filter(models.Doctor.id == doc_id).first()
            doc.available = True
            db.commit()
        finally:
            db.close()

        # 3. Booking on doctor's approved leave dates (should fail with 400)
        # Create an approved leave request for future_str
        db = TestingSessionLocal()
        try:
            leave = models.LeaveRequest(
                doctor_id=doc_id,
                start_date=future_str,
                end_date=future_str,
                reason="Medical conference",
                status="approved"
            )
            db.add(leave)
            db.commit()
        finally:
            db.close()

        resp_leave = client.post(
            "/appointment/book",
            headers=patient_headers,
            json={
                "doctor_id": doc_id,
                "date": future_str,
                "time": "12:00"
            }
        )
        assert resp_leave.status_code == 400
        assert "approved leave" in resp_leave.json()["detail"].lower()

        # Check notification was created for doctor
        db = TestingSessionLocal()
        try:
            notif = db.query(models.Notification).filter(models.Notification.user_id == doctor_user_id).first()
            assert notif is not None
            assert "leave" in notif.message.lower()
            db.delete(notif)
            db.commit()
        finally:
            db.close()

        # Delete the leave request so it doesn't block next tests
        db = TestingSessionLocal()
        try:
            leave = db.query(models.LeaveRequest).filter(models.LeaveRequest.doctor_id == doc_id).first()
            db.delete(leave)
            db.commit()
        finally:
            db.close()

        # 4. Double booking (should fail with 400)
        # Book a valid appointment at future_str at 14:00
        resp_valid = client.post(
            "/appointment/book",
            headers=patient_headers,
            json={
                "doctor_id": doc_id,
                "date": future_str,
                "time": "14:00"
            }
        )
        assert resp_valid.status_code == 201

        # Attempt to book the same slot again
        resp_double = client.post(
            "/appointment/book",
            headers=patient_headers,
            json={
                "doctor_id": doc_id,
                "date": future_str,
                "time": "14:00"
            }
        )
        assert resp_double.status_code == 400
        assert "already booked" in resp_double.json()["detail"].lower()

        # Check notification was created for doctor
        db = TestingSessionLocal()
        try:
            notif = db.query(models.Notification).filter(models.Notification.user_id == doctor_user_id).first()
            assert notif is not None
            assert "conflicts with an existing booking" in notif.message
        finally:
            db.close()

        print("\n=== BOOKING RULES & CONFLICT NOTIFICATIONS INTEGRATION TESTS PASSED ===")
    finally:
        teardown_module()

if __name__ == "__main__":
    test_appointment_booking_rules_and_notifications()
