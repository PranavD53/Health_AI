import os
import shutil
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///./test_healthcare_new.db"
os.environ["SECRET_KEY"] = "test_secret_key_12345"
os.environ["GROQ_API_KEY"] = "gsk_mockkeyforlocaltesting"

from app.main import app
from app.database import Base, get_db
from app import models

# Create test database engine
engine = create_engine("sqlite:///./test_healthcare_new.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db
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
    
    # Create uploads directory
    os.makedirs("uploads", exist_ok=True)

def teardown_module():
    global engine
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        print(f"Warning dropping metadata: {e}")
    engine.dispose()
    if os.path.exists("test_healthcare_new.db"):
        try:
            os.remove("test_healthcare_new.db")
        except Exception as e:
            print(f"Warning removing DB file: {e}")
    # Clean up test files in uploads
    if os.path.exists("uploads"):
        for f in os.listdir("uploads"):
            if f.startswith("Prescription_") or f.startswith("test_record"):
                try:
                    os.remove(os.path.join("uploads", f))
                except Exception:
                    pass

def test_new_endpoints():
    setup_module()
    try:
        print("\n--- Testing New Endpoints (Prescription & AI Record Analysis) ---")

        # 1. Register and Login Patient
        print("Registering & logging in Patient...")
        patient_reg = client.post("/auth/register", json={
            "email": "test_patient@example.com",
            "password": "patientpassword",
            "role": "patient"
        })
        assert patient_reg.status_code == 201, patient_reg.text
        patient_id = patient_reg.json()["id"]
        
        patient_login = client.post("/auth/login", json={
            "email": "test_patient@example.com",
            "password": "patientpassword"
        })
        assert patient_login.status_code == 200, patient_login.text
        patient_headers = {"Authorization": f"Bearer {patient_login.json()['access_token']}"}

        # 2. Register and Login Doctor
        print("Registering & logging in Doctor...")
        doctor_reg = client.post("/auth/register", json={
            "email": "test_doctor@example.com",
            "password": "doctorpassword",
            "role": "doctor"
        })
        assert doctor_reg.status_code == 201, doctor_reg.text
        doctor_id = doctor_reg.json()["id"]
        
        doctor_login = client.post("/auth/login", json={
            "email": "test_doctor@example.com",
            "password": "doctorpassword"
        })
        assert doctor_login.status_code == 200, doctor_login.text
        doctor_headers = {"Authorization": f"Bearer {doctor_login.json()['access_token']}"}

        # Register doctor profile to seeded list so name works
        db = TestingSessionLocal()
        try:
            # Let's seed a doctor record in db for this user
            new_doc = models.Doctor(
                user_id=doctor_id,
                name="Dr. Evan Wright",
                specialization="Pediatrics",
                location="Children's Clinic, 12 Maple St",
                experience_years=10,
                available=True,
                contact="test_doctor@example.com",
                license_number="MD-EVAN-10"
            )
            db.add(new_doc)
            db.commit()
        finally:
            db.close()

        # 3. Start Conversation between Patient and Doctor
        print("Starting conversation between Doctor and Patient...")
        conv_start = client.post("/chats/conversations/start", headers=patient_headers, json={
            "target_user_id": doctor_id
        })
        assert conv_start.status_code in [200, 201], conv_start.text
        conversation_id = conv_start.json()["id"]

        # 4. Test POST /chats/conversations/{conversation_id}/prescription
        print("Testing Online Clinical Prescription Endpoint...")
        prescription_payload = {
            "patient_name": "Test Patient",
            "diagnosis": "Seasonal Influenza",
            "medicines": [
                {"name": "Oseltamivir", "dosage": "75 mg", "frequency": "1-0-1", "duration": "5 days"},
                {"name": "Paracetamol", "dosage": "500 mg", "frequency": "1-1-1", "duration": "3 days"}
            ],
            "instructions": "Drink plenty of water and rest."
        }
        presc_resp = client.post(
            f"/chats/conversations/{conversation_id}/prescription",
            headers=doctor_headers,
            json=prescription_payload
        )
        assert presc_resp.status_code == 200, presc_resp.text
        assert presc_resp.json()["attachment_name"].startswith("Prescription_")
        assert presc_resp.json()["attachment_path"].startswith("/uploads/Prescription_")
        assert "Clinical prescription" in presc_resp.json()["content"]
        
        # Verify file exists on disk
        presc_filepath = os.path.join(os.getcwd(), presc_resp.json()["attachment_path"].lstrip("/"))
        assert os.path.exists(presc_filepath)
        with open(presc_filepath, "r", encoding="utf-8") as f:
            file_content = f.read()
            assert "Dr. Evan Wright" in file_content
            assert "Oseltamivir" in file_content
            assert "Seasonal Influenza" in file_content
        print("[OK] Online Prescription successfully created, saved to disk, and attached to chat")

        # 5. Test POST /records/{id}/analyze (AI Insights)
        # First write a fake medical record to disk
        record_filename = "test_record_report.txt"
        record_filepath = os.path.join("uploads", record_filename)
        with open(record_filepath, "w", encoding="utf-8") as f:
            f.write("Patient: Test Patient\nBlood Report: WBC 14.5 K/uL (Abnormal High), Hemoglobin 14.2 g/dL\nSymptom: Fever and persistent cough.")
            
        db = TestingSessionLocal()
        try:
            # Insert medical record in db
            new_record = models.MedicalRecord(
                user_id=patient_id,
                file_name=record_filename,
                file_path=f"/uploads/{record_filename}",
                file_type="text/plain",
                fraud_status="VERIFIED (Authentic)"
            )
            db.add(new_record)
            db.commit()
            db.refresh(new_record)
            record_id = new_record.id
        finally:
            db.close()
            
        print("Testing AI Record Analysis Endpoint...")
        import unittest.mock as mock
        
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"insights": "Elevated white blood cell count indicates infection.", "medications": "Suggesting safe rest and fever reducers.", "disclaimer": "AI generated warning."}'
                }
            }]
        }
        
        with mock.patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
            analyze_resp = client.post(f"/records/{record_id}/analyze", headers=patient_headers)
            assert analyze_resp.status_code == 200, analyze_resp.text
            assert "insights" in analyze_resp.json()
            assert "medications" in analyze_resp.json()
            assert "disclaimer" in analyze_resp.json()
            assert analyze_resp.json()["insights"] == "Elevated white blood cell count indicates infection."
            
        print("[OK] AI Medical Record Analysis mock-test passed successfully")

        print("\n=== NEW ENDPOINTS TESTS PASSED SUCCESSFULLY ===")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Unexpected error in test run: {e}")
        raise
    finally:
        teardown_module()

if __name__ == "__main__":
    test_new_endpoints()
