import os
import shutil
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test_secret_key_12345"
os.environ["UPLOADS_DIR"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_uploads")

from app.main import app
from app.database import Base, get_db
from app import models
from app.config import UPLOADS_DIR

# Create test database engine
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency to point to the test database
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    # Create tables
    Base.metadata.create_all(bind=engine)
    # Seed doctors table in testing DB
    from app.routes.doctors import seed_doctors
    from app.main import seed_demo_users
    db = TestingSessionLocal()
    try:
        seed_doctors(db)
        seed_demo_users(db)
    finally:
        db.close()

def teardown_module():
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
    # Drop tables
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        print(f"Warning dropping tables: {e}")
    engine.dispose()

def test_feedback_system():
    setup_module()
    try:
        print("Registering patient...")
        reg_patient = client.post("/auth/register", json={
            "email": "feedback_patient@test.com",
            "password": "password123",
            "role": "patient"
        })
        assert reg_patient.status_code == 201, reg_patient.text
        
        login_patient = client.post("/auth/login", json={
            "email": "feedback_patient@test.com",
            "password": "password123"
        })
        assert login_patient.status_code == 200, login_patient.text
        patient_token = login_patient.json()["access_token"]
        patient_headers = {"Authorization": f"Bearer {patient_token}"}
        
        # Create Patient Profile
        profile_resp = client.post("/profile", headers=patient_headers, json={
            "name": "Jane Patient",
            "date_of_birth": "1995-08-20",
            "gender": "female",
            "height": 165.0,
            "weight": 60.0
        })
        assert profile_resp.status_code == 201

        # Register/Get a doctor
        doctors_resp = client.get("/doctors", headers=patient_headers)
        assert doctors_resp.status_code == 200
        doctors_list = doctors_resp.json()
        assert len(doctors_list) > 0
        doctor_id = doctors_list[0]["id"]
        doctor_user_id = doctors_list[0]["user_id"]
        
        # Book Appointment
        book_resp = client.post("/appointment/book", headers=patient_headers, json={
            "doctor_id": doctor_id,
            "date": "2026-07-21",
            "time": "10:00"
        })
        assert book_resp.status_code == 201
        appointment_id = book_resp.json()["id"]
        
        # 1. Try to submit feedback before appointment is completed -> Expect 400 Bad Request
        bad_feedback_resp = client.post("/feedback/submit", headers=patient_headers, json={
            "appointment_id": appointment_id,
            "rating_overall": 5,
            "rating_doctor": 5,
            "comments": "Great service!"
        })
        assert bad_feedback_resp.status_code == 400
        assert "Feedback can only be submitted after the appointment is completed" in bad_feedback_resp.json()["detail"]
        
        # 2. Complete appointment (as patient)
        complete_resp = client.post(f"/appointment/complete/{appointment_id}", headers=patient_headers)
        assert complete_resp.status_code == 200
        assert complete_resp.json()["status"] == "success"
        
        # Try to complete it again -> Expect 400 Bad Request
        complete_again = client.post(f"/appointment/complete/{appointment_id}", headers=patient_headers)
        assert complete_again.status_code == 400
        
        # Check pending feedback endpoint -> Should list this appointment
        pending_resp = client.get("/feedback/pending", headers=patient_headers)
        assert pending_resp.status_code == 200
        pending_list = pending_resp.json()
        assert any(appt["id"] == appointment_id for appt in pending_list)
        
        # 3. Submit feedback with invalid ratings (e.g. > 5) -> Expect 422 Unprocessable Entity
        invalid_feedback = client.post("/feedback/submit", headers=patient_headers, json={
            "appointment_id": appointment_id,
            "rating_overall": 6,
            "rating_doctor": 5
        })
        assert invalid_feedback.status_code == 422
        
        # 4. Submit feedback with valid ratings
        feedback_payload = {
            "appointment_id": appointment_id,
            "rating_overall": 4,
            "rating_doctor": 5,
            "comments": "Very good doctor consultation",
            "rating_communication": 5,
            "rating_professionalism": 4,
            "rating_wait_time": 3,
            "rating_satisfaction": 4
        }
        submit_resp = client.post("/feedback/submit", headers=patient_headers, json=feedback_payload)
        assert submit_resp.status_code == 201, submit_resp.text
        feedback_data = submit_resp.json()
        assert feedback_data["rating_overall"] == 4
        assert feedback_data["rating_doctor"] == 5
        assert feedback_data["comments"] == "Very good doctor consultation"
        assert feedback_data["rating_communication"] == 5
        assert feedback_data["is_approved"] is True
        
        # 5. Try to submit feedback again (no edit param) -> Expect 400
        duplicate_resp = client.post("/feedback/submit", headers=patient_headers, json=feedback_payload)
        assert duplicate_resp.status_code == 400
        assert "Feedback has already been submitted" in duplicate_resp.json()["detail"]
        
        # 6. Edit the feedback (with edit=true query param)
        feedback_payload["comments"] = "Actually, exceptional service!"
        feedback_payload["rating_overall"] = 5
        edit_resp = client.post("/feedback/submit?edit=true", headers=patient_headers, json=feedback_payload)
        assert edit_resp.status_code == 201, edit_resp.text
        assert edit_resp.json()["comments"] == "Actually, exceptional service!"
        assert edit_resp.json()["rating_overall"] == 5
        
        # 7. Get feedback for appointment
        get_fb_resp = client.get(f"/feedback/appointment/{appointment_id}", headers=patient_headers)
        assert get_fb_resp.status_code == 200
        assert get_fb_resp.json()["comments"] == "Actually, exceptional service!"
        
        # 8. Check pending feedback endpoint -> Should be empty now
        pending_resp_after = client.get("/feedback/pending", headers=patient_headers)
        assert pending_resp_after.status_code == 200
        assert not any(appt["id"] == appointment_id for appt in pending_resp_after.json())
        
        # 9. Get doctor reviews from patient perspective -> Should be visible since is_approved is True
        reviews_resp = client.get(f"/feedback/doctor/{doctor_id}", headers=patient_headers)
        assert reviews_resp.status_code == 200
        assert len(reviews_resp.json()) == 1
        assert reviews_resp.json()[0]["comments"] == "Actually, exceptional service!"
        
        # 10. Patient retrieves doctor analytics -> Expect 403 Forbidden
        analytics_fail = client.get(f"/feedback/doctor/{doctor_id}/analytics", headers=patient_headers)
        assert analytics_fail.status_code == 403
        
        # 11. Log in as the doctor to check analytics
        db = TestingSessionLocal()
        try:
            doc_user = db.query(models.User).filter(models.User.id == doctor_user_id).first()
            doc_email = doc_user.email if doc_user else "doctor@test.com"
        finally:
            db.close()
            
        login_doc = client.post("/auth/login", json={
            "email": doc_email,
            "password": "Password123!" # Seed users default password
        })
        assert login_doc.status_code == 200
        doc_token = login_doc.json()["access_token"]
        doc_headers = {"Authorization": f"Bearer {doc_token}"}
        
        # Doctor views their own analytics
        analytics_resp = client.get(f"/feedback/doctor/{doctor_id}/analytics", headers=doc_headers)
        assert analytics_resp.status_code == 200
        analytics_data = analytics_resp.json()
        assert analytics_data["total_reviews"] == 1
        assert analytics_data["average_overall"] == 5.0
        assert analytics_data["average_doctor"] == 5.0
        assert analytics_data["average_communication"] == 5.0
        assert analytics_data["average_professionalism"] == 4.0
        
        # 12. Admin Moderation Check
        # Register and log in as admin
        client.post("/auth/register", json={
            "email": "admin_fb@test.com",
            "password": "adminpassword",
            "role": "admin"
        })
        login_admin = client.post("/auth/login", json={
            "email": "admin_fb@test.com",
            "password": "adminpassword"
        })
        assert login_admin.status_code == 200
        admin_token = login_admin.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get all feedback (admin)
        admin_all_resp = client.get("/feedback/admin/all", headers=admin_headers)
        assert admin_all_resp.status_code == 200
        assert len(admin_all_resp.json()) >= 1
        
        # Moderate review: set is_approved = False
        feedback_db_id = feedback_data["id"]
        mod_resp = client.post(f"/feedback/admin/moderate/{feedback_db_id}?is_approved=false", headers=admin_headers)
        assert mod_resp.status_code == 200
        assert mod_resp.json()["is_approved"] is False
        
        # Public / Patient views doctor reviews -> Should be hidden now
        reviews_resp_after = client.get(f"/feedback/doctor/{doctor_id}", headers=patient_headers)
        assert reviews_resp_after.status_code == 200
        assert len(reviews_resp_after.json()) == 0
        
        # Moderate review back to is_approved = True
        mod_resp_true = client.post(f"/feedback/admin/moderate/{feedback_db_id}?is_approved=true", headers=admin_headers)
        assert mod_resp_true.status_code == 200
        assert mod_resp_true.json()["is_approved"] is True
        
        # Patient views doctor reviews -> Visible again
        reviews_resp_after_true = client.get(f"/feedback/doctor/{doctor_id}", headers=patient_headers)
        assert len(reviews_resp_after_true.json()) == 1

        print("Feedback system integration tests completed successfully.")
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Unexpected error in test run: {e}")
        raise
    finally:
        teardown_module()

if __name__ == "__main__":
    test_feedback_system()
