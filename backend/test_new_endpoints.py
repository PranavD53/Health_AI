import os
import shutil
import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test_secret_key_12345")
os.environ["GROQ_API_KEY"] = os.environ.get("GROQ_API_KEY", "gsk_mockkeyforlocaltesting")
os.environ["UPLOADS_DIR"] = os.environ.get("UPLOADS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_uploads"))

from app.main import app
from app.database import Base, get_db, engine, SessionLocal as TestingSessionLocal
from app import models
from app.config import UPLOADS_DIR

# Override get_db
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

CREATED_TEST_FILES = set()

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
    
    # Create uploads directory
    if os.path.exists(UPLOADS_DIR):
        shutil.rmtree(UPLOADS_DIR)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def teardown_module():
    global engine
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
    _cleanup_db(engine, Base)
    engine.dispose()
    if os.path.exists("test_healthcare_new.db"):
        try:
            os.remove("test_healthcare_new.db")
        except Exception as e:
            print(f"Warning removing DB file: {e}")
    # Clean up test uploads directory
    if os.path.exists(UPLOADS_DIR):
        try:
            shutil.rmtree(UPLOADS_DIR)
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
        assert presc_resp.json()["attachment_name"].endswith(".pdf")
        assert presc_resp.json()["attachment_path"].startswith("/uploads/Prescription_")
        assert presc_resp.json()["attachment_path"].endswith(".pdf")
        assert "Clinical prescription" in presc_resp.json()["content"]
        
        # Verify PDF can be fetched via endpoint and contains expected clinical content
        filename = presc_resp.json()["attachment_name"]
        download_resp = client.get(f"/uploads/{filename}")
        assert download_resp.status_code == 200
        pdf_bytes = download_resp.content
        assert pdf_bytes.startswith(b"%PDF")
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            assert "Dr. Evan Wright" in pdf_text or "Evan Wright" in pdf_text
            assert "Oseltamivir" in pdf_text
            assert "Seasonal Influenza" in pdf_text
            assert "Digital Signature ID" in pdf_text
        except ImportError:
            pass
        print("[OK] Online Prescription successfully created and verified in-memory")

        # 5. Test POST /records/{id}/analyze (AI Insights)
        import base64
        record_filename = "test_record_report.txt"
        record_content = "Patient: Test Patient\nBlood Report: WBC 14.5 K/uL (Abnormal High), Hemoglobin 14.2 g/dL\nSymptom: Fever and persistent cough."
        encoded_content = base64.b64encode(record_content.encode("utf-8")).decode("utf-8")
            
        db = TestingSessionLocal()
        try:
            # Insert medical record in db
            new_record = models.MedicalRecord(
                user_id=patient_id,
                file_name=record_filename,
                file_path=f"/uploads/{record_filename}",
                file_type="text/plain",
                file_data=encoded_content,
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

        # 5.5. Test POST /records/{id}/anti-fraud (Anti-Fraud Scan)
        print("Testing Anti-Fraud Scan Endpoint...")
        anti_fraud_resp = client.post(f"/records/{record_id}/anti-fraud", headers=patient_headers)
        assert anti_fraud_resp.status_code == 200, anti_fraud_resp.text
        assert "fraud_status" in anti_fraud_resp.json()
        assert "reason" in anti_fraud_resp.json()
        assert anti_fraud_resp.json()["fraud_status"] == "VERIFIED (Authentic)"
        print("[OK] Anti-Fraud Scan endpoint test passed successfully")

        # 6. Test that prescription generated is in patient's records
        print("Verifying prescription recorded in medical records...")
        records_resp = client.get("/records/my-records", headers=patient_headers)
        assert records_resp.status_code == 200, records_resp.text
        patient_records = records_resp.json()
        assert len(patient_records) > 0
        presc_record = next((r for r in patient_records if "Prescription_" in r["file_name"]), None)
        assert presc_record is not None, "Prescription not found in patient's medical records"
        assert presc_record["file_type"] == "application/pdf"

        # 7. Test uploading file in chat and storing it as Medical Record
        print("Testing file upload in chat & storage as medical record...")
        chat_filename = "test_record_chat_uploaded.png"
        chat_filepath = os.path.join(UPLOADS_DIR, chat_filename)
        CREATED_TEST_FILES.add(chat_filepath)
        with open(chat_filepath, "wb") as f:
            f.write(b"PNG_FAKE_IMAGE_DATA")
            
        with open(chat_filepath, "rb") as f:
            chat_upload_resp = client.post(
                f"/chats/conversations/{conversation_id}/send",
                headers=patient_headers,
                data={"content": "Here is my report image"},
                files={"file": (chat_filename, f, "image/png")}
            )
        assert chat_upload_resp.status_code == 200, chat_upload_resp.text
        if "attachment_path" in chat_upload_resp.json() and chat_upload_resp.json()["attachment_path"]:
            CREATED_TEST_FILES.add(chat_upload_resp.json()["attachment_path"].lstrip("/"))
        msg_id = chat_upload_resp.json()["id"]
        
        # Verify it got saved to patient's medical records
        records_resp = client.get("/records/my-records", headers=patient_headers)
        patient_records = records_resp.json()
        chat_record = next((r for r in patient_records if r["file_name"] == chat_filename), None)
        assert chat_record is not None, "Chat uploaded file not saved to patient's medical records"
        assert chat_record["file_type"] == "image/png"
        assert chat_record["fraud_status"] == "VERIFIED (Authentic)"

        # 8. Test deleting a medical record
        print("Testing DELETE /records/{id}...")
        del_record_id = chat_record["id"]
        del_resp = client.delete(f"/records/{del_record_id}", headers=patient_headers)
        assert del_resp.status_code == 200, del_resp.text
        # Verify it is deleted from db
        records_resp = client.get("/records/my-records", headers=patient_headers)
        assert not any(r["id"] == del_record_id for r in records_resp.json())
        
        # 9. Test deleting a chat message
        print("Testing DELETE /chats/conversations/{id}/messages/{msg_id}...")
        del_msg_resp = client.delete(f"/chats/conversations/{conversation_id}/messages/{msg_id}", headers=patient_headers)
        assert del_msg_resp.status_code == 200, del_msg_resp.text
        
        # 10. Test deleting conversation
        print("Testing DELETE /chats/conversations/{id}...")
        del_conv_resp = client.delete(f"/chats/conversations/{conversation_id}", headers=patient_headers)
        assert del_conv_resp.status_code == 200, del_conv_resp.text

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
