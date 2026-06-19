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

# Initialize client
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
    # Clear uploads directory for tests
    if os.path.exists(UPLOADS_DIR):
        shutil.rmtree(UPLOADS_DIR)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

def teardown_module():
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
    # Drop tables and remove test DB
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        print(f"Warning dropping tables: {e}")
    engine.dispose()
    if os.path.exists("./test_healthcare.db"):
        try:
            os.remove("./test_healthcare.db")
        except Exception as e:
            print(f"Warning removing DB file: {e}")
    # Clean up uploads directory
    if os.path.exists(UPLOADS_DIR):
        try:
            shutil.rmtree(UPLOADS_DIR)
        except Exception as e:
            print(f"Warning clearing uploads directory: {e}")

def test_healthcare_backend():
    print("\n--- Starting API Integrations Tests ---")
    setup_module()
    
    try:
        # 1. Register a Patient
        print("Testing /auth/register...")
        reg_response = client.post("/auth/register", json={
            "email": "patient@test.com",
            "password": "password123",
            "role": "patient"
        })
        assert reg_response.status_code == 201, reg_response.text
        assert reg_response.json()["email"] == "patient@test.com"
        assert reg_response.json()["role"] == "patient"
        print("[OK] Register Patient successful")

        # 2. Login the Patient
        print("Testing /auth/login...")
        login_response = client.post("/auth/login", json={
            "email": "patient@test.com",
            "password": "password123"
        })
        assert login_response.status_code == 200, login_response.text
        token_data = login_response.json()
        assert "access_token" in token_data
        assert token_data["role"] == "patient"
        patient_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        print("[OK] Login Patient successful")

        # 3. Create Patient Profile
        print("Testing POST /profile...")
        profile_response = client.post("/profile", headers=patient_headers, json={
            "name": "John Doe",
            "date_of_birth": "1990-05-15",
            "gender": "male",
            "height": 178.5,
            "weight": 75.0,
            "allergies": "Peanuts",
            "existing_conditions": "None"
        })
        assert profile_response.status_code == 201, profile_response.text
        assert profile_response.json()["name"] == "John Doe"
        print("[OK] Profile creation successful")

        # 4. Get Patient Profile
        print("Testing GET /profile...")
        get_profile_response = client.get("/profile", headers=patient_headers)
        assert get_profile_response.status_code == 200, get_profile_response.text
        assert get_profile_response.json()["allergies"] == "Peanuts"
        print("[OK] Get Profile successful")

        # 5. List Doctors and Filter by Specialization
        print("Testing GET /doctors...")
        # Since startup trigger was run on client setup, check doctors
        doctors_response = client.get("/doctors", headers=patient_headers)
        assert doctors_response.status_code == 200, doctors_response.text
        doctors_list = doctors_response.json()
        assert len(doctors_list) > 0
        doctor_id = doctors_list[0]["id"]
        
        # Test filtering
        filter_response = client.get(f"/doctors?specialization={doctors_list[0]['specialization']}", headers=patient_headers)
        assert filter_response.status_code == 200
        assert len(filter_response.json()) > 0
        print("[OK] Doctors listing and filtering successful")

        # 6. Book Appointment
        print("Testing POST /appointment/book...")
        book_response = client.post("/appointment/book", headers=patient_headers, json={
            "doctor_id": doctor_id,
            "date": "2026-07-20",
            "time": "14:30"
        })
        assert book_response.status_code == 201, book_response.text
        appointment_id = book_response.json()["id"]
        assert book_response.json()["status"] == "booked"
        print("[OK] Book Appointment successful")

        # 7. Get My Appointments
        print("Testing GET /appointment/my-appointments...")
        my_appts_response = client.get("/appointment/my-appointments", headers=patient_headers)
        assert my_appts_response.status_code == 200, my_appts_response.text
        assert len(my_appts_response.json()) == 1
        print("[OK] Get My Appointments successful")

        # 8. Analyze Routine Symptoms
        print("Testing POST /symptom/analyze (Routine)...")
        symp_response = client.post("/symptom/analyze", headers=patient_headers, json={
            "symptoms": "Mild headache and runny nose",
            "severity": "mild",
            "duration": "2 days"
        })
        assert symp_response.status_code == 200, symp_response.text
        symp_data = symp_response.json()
        assert symp_data["emergency_alert"] is False
        assert symp_data["symptom_log"]["risk_category"] in ["Self-Care", "Routine", "Urgent"]
        print("[OK] Symptom analysis (Routine) successful")

        # 9. Analyze Emergency Symptoms
        print("Testing POST /symptom/analyze (Emergency)...")
        em_response = client.post("/symptom/analyze", headers=patient_headers, json={
            "symptoms": "Severe chest pain and sudden stroke-like symptoms",
            "severity": "severe",
            "duration": "10 minutes"
        })
        assert em_response.status_code == 200, em_response.text
        em_data = em_response.json()
        assert em_data["emergency_alert"] is True
        assert em_data["symptom_log"]["risk_category"] == "Emergency"
        assert "108" in em_data["alert_message"]
        print("[OK] Symptom analysis (Emergency) successful")

        # 10. Start Conversation
        print("Testing POST /conversations...")
        conv_response = client.post("/conversations", headers=patient_headers, json={
            "title": "General Health Checkup Inquiry"
        })
        assert conv_response.status_code == 201, conv_response.text
        conv_id = conv_response.json()["id"]
        print("[OK] Start Conversation successful")

        # 11. Send Messages (Regular and Emergency)
        print("Testing POST /conversations/{id}/messages...")
        # Normal query
        msg_response = client.post(f"/conversations/{conv_id}/messages", headers=patient_headers, json={
            "content": "What are the common benefits of eating green vegetables daily?"
        })
        assert msg_response.status_code == 200, msg_response.text
        assert "Disclaimer" in msg_response.json()["content"]
        
        # Emergency query
        em_msg_response = client.post(f"/conversations/{conv_id}/messages", headers=patient_headers, json={
            "content": "Help me, I am having sudden chest pain and cannot breathe"
        })
        assert em_msg_response.status_code == 200, em_msg_response.text
        assert "EMERGENCY" in em_msg_response.json()["content"]
        print("[OK] Conversation messages and safety filters successful")

        # 12. Upload Medical Record File
        print("Testing POST /records/upload...")
        # Create a dummy file
        dummy_file_path = "test_record.pdf"
        with open(dummy_file_path, "w") as f:
            f.write("Dummy medical record content PDF")

        with open(dummy_file_path, "rb") as f:
            upload_response = client.post(
                "/records/upload",
                headers=patient_headers,
                files={"file": ("test_record.pdf", f, "application/pdf")}
            )
        assert upload_response.status_code == 201, upload_response.text
        assert upload_response.json()["file_name"] == "test_record.pdf"
        os.remove(dummy_file_path)
        print("[OK] Medical record upload successful")

        # 13. Get Dashboard Summary
        print("Testing GET /dashboard-data...")
        dash_response = client.get("/dashboard-data", headers=patient_headers)
        assert dash_response.status_code == 200, dash_response.text
        dash_data = dash_response.json()
        assert len(dash_data["upcoming_appointments"]) > 0
        assert len(dash_data["recent_symptom_logs"]) > 0
        assert len(dash_data["medical_records"]) > 0
        assert "health_tip" in dash_data
        print("[OK] Dashboard retrieval successful")

        # 14. Admin Role Checks (Register and Access Audit Logs)
        print("Testing Admin registration and Role-Based Access Control...")
        admin_reg = client.post("/auth/register", json={
            "email": "admin@test.com",
            "password": "adminpassword",
            "role": "admin"
        })
        assert admin_reg.status_code == 201
        
        admin_login = client.post("/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpassword"
        })
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        # Patient attempts to access audit logs -> Expect 403 Forbidden
        patient_audit_response = client.get("/audit/logs", headers=patient_headers)
        assert patient_audit_response.status_code == 403
        
        # Admin attempts to access audit logs -> Expect 200 OK
        admin_audit_response = client.get("/audit/logs", headers=admin_headers)
        assert admin_audit_response.status_code == 200
        logs = admin_audit_response.json()
        assert len(logs) > 0
        # Verify specific actions were logged
        actions = [log["action"] for log in logs]
        assert "REGISTER" in actions
        assert "LOGIN" in actions
        assert "CREATE_PROFILE" in actions
        assert "EMERGENCY_DETECTED" in actions
        print("[OK] Admin role and audit logs verification successful")

        # 15. Cancel Appointment
        print("Testing DELETE /appointment/cancel/{id}...")
        cancel_response = client.delete(f"/appointment/cancel/{appointment_id}", headers=patient_headers)
        assert cancel_response.status_code == 200, cancel_response.text
        
        # Verify appointment is marked as cancelled
        my_appts_response2 = client.get("/appointment/my-appointments", headers=patient_headers)
        assert my_appts_response2.json()[0]["status"] == "cancelled"

        # 16. Test Patient Metrics API
        print("Testing Patient Metrics APIs...")
        metric_get = client.get("/dashboard/metrics", headers=patient_headers)
        assert metric_get.status_code == 200
        assert "heart_rate" in metric_get.json()
        
        metric_log = client.post("/dashboard/metrics", headers=patient_headers, json={
            "metric_type": "heart_rate",
            "value": "78 bpm"
        })
        assert metric_log.status_code == 200
        
        metric_get2 = client.get("/dashboard/metrics", headers=patient_headers)
        assert metric_get2.json()["heart_rate"] == "78 bpm"
        print("[OK] Patient Metrics successful")

        # 17. Register & Test Doctor Dashboard
        print("Testing Doctor Dashboard...")
        doc_reg = client.post("/auth/register", json={
            "email": "doctor@test.com",
            "password": "doctorpassword",
            "role": "doctor"
        })
        assert doc_reg.status_code == 201
        
        doc_login = client.post("/auth/login", json={
            "email": "doctor@test.com",
            "password": "doctorpassword"
        })
        doc_headers = {"Authorization": f"Bearer {doc_login.json()['access_token']}"}
        
        doc_dash = client.get("/doctor/dashboard", headers=doc_headers)
        assert doc_dash.status_code == 200
        assert "upcoming_appointments" in doc_dash.json()
        print("[OK] Doctor Dashboard successful")

        # 18. Test Admin Dashboard
        print("Testing Admin Dashboard...")
        admin_dash = client.get("/admin/dashboard", headers=admin_headers)
        assert admin_dash.status_code == 200
        assert "verification_queue" in admin_dash.json()
        assert "users" in admin_dash.json()
        print("[OK] Admin Dashboard successful")

        # 19. Test Global Assistant Chat API
        print("Testing Global Assistant Chat API...")
        assist_resp = client.post("/ai/assistant", headers=patient_headers, json={
            "message": "Hello, find a doctor for me"
        })
        assert assist_resp.status_code == 200
        # Parse SSE data
        response_text = assist_resp.text
        if "data:" in response_text:
            import json
            data_json = None
            for line in response_text.splitlines():
                if line.startswith("data:"):
                    try:
                        parsed = json.loads(line.replace("data:", "").strip())
                        if parsed.get("type") == "action":
                            data_json = parsed
                            break
                    except Exception:
                        pass
            assert data_json is not None, f"Action response block not found in SSE stream: {response_text}"
            assert "reply" in data_json
            assert "disclaimer" in data_json
        else:
            assert "reply" in assist_resp.json()
        print("[OK] Global Assistant Chat successful")

        # 20. Test Admin Request, Approval, Rejection, and Deletion
        print("Testing Admin promotion request, approval, rejection, and deletion...")
        
        # Superadmin login
        superadmin_login = client.post("/auth/login", json={
            "email": "sricharanpranav1@gmail.com",
            "password": "Pranav@123"
        })
        assert superadmin_login.status_code == 200, "Superadmin login failed"
        superadmin_headers = {"Authorization": f"Bearer {superadmin_login.json()['access_token']}"}
        
        # Register a doctor to promote (since patients cannot request admin)
        promo_doctor_reg = client.post("/auth/register", json={
            "email": "promo_doctor@test.com",
            "password": "password123",
            "role": "doctor"
        })
        assert promo_doctor_reg.status_code == 201
        promo_user_id = promo_doctor_reg.json()["id"]
        
        promo_login = client.post("/auth/login", json={
            "email": "promo_doctor@test.com",
            "password": "password123"
        })
        assert promo_login.status_code == 200
        promo_doctor_headers = {"Authorization": f"Bearer {promo_login.json()['access_token']}"}
        
        # Patient attempts to request admin -> should fail with 403
        req_promo_fail = client.post("/auth/request-admin", headers=patient_headers)
        assert req_promo_fail.status_code == 403
        
        # 1. Doctor requests admin promotion
        req_promo_resp = client.post("/auth/request-admin", headers=promo_doctor_headers)
        assert req_promo_resp.status_code == 200
        assert req_promo_resp.json()["status"] == "success"
        
        # Verify admin_requested is true on dashboard query
        dash_response_promo = client.get("/admin/dashboard", headers=superadmin_headers)
        assert dash_response_promo.status_code == 200
        users_list = dash_response_promo.json()["users"]
        promo_user_data = next(u for u in users_list if u["id"] == promo_user_id)
        assert promo_user_data["admin_requested"] is True
        
        # 2. Reject request by superadmin
        reject_promo_resp = client.post(f"/auth/admin/reject-admin/{promo_user_id}", headers=superadmin_headers)
        assert reject_promo_resp.status_code == 200
        
        # Check it is false now
        dash_response_promo2 = client.get("/admin/dashboard", headers=superadmin_headers)
        promo_user_data2 = next(u for u in dash_response_promo2.json()["users"] if u["id"] == promo_user_id)
        assert promo_user_data2["admin_requested"] is False
        
        # 3. Request again and Approve request by superadmin
        req_promo_resp2 = client.post("/auth/request-admin", headers=promo_doctor_headers)
        assert req_promo_resp2.status_code == 200
        
        approve_promo_resp = client.post(f"/auth/admin/approve-admin/{promo_user_id}", headers=superadmin_headers)
        assert approve_promo_resp.status_code == 200
        
        # Verify role has updated to admin
        dash_response_promo3 = client.get("/admin/dashboard", headers=superadmin_headers)
        promo_user_data3 = next(u for u in dash_response_promo3.json()["users"] if u["id"] == promo_user_id)
        assert promo_user_data3["role"] == "admin"
        
        # 4. Try to approve using normal admin (like admin@test.com) -> should fail with 403
        req_promo_resp_fail = client.post(f"/auth/admin/approve-admin/{promo_user_id}", headers=admin_headers)
        assert req_promo_resp_fail.status_code == 403
        
        # 5. Cascading user delete
        delete_user_resp = client.delete(f"/auth/admin/users/{promo_user_id}", headers=superadmin_headers)
        assert delete_user_resp.status_code == 200
        
        # Verify user is gone from admin dashboard
        dash_response_promo4 = client.get("/admin/dashboard", headers=superadmin_headers)
        assert not any(u["id"] == promo_user_id for u in dash_response_promo4.json()["users"])
        
        # 6. Test forgot password flow
        forgot_resp = client.post("/auth/forgot-password", json={"email": "patient@test.com"})
        assert forgot_resp.status_code == 200
        assert forgot_resp.json()["status"] == "success"
        
        db = TestingSessionLocal()
        try:
            from app import models
            user_record = db.query(models.User).filter(models.User.email == "patient@test.com").first()
            assert user_record is not None
            test_otp_code = user_record.otp
        finally:
            db.close()
            
        verify_forgot_resp = client.post("/auth/forgot-password-verify", json={
            "email": "patient@test.com",
            "otp": test_otp_code
        })
        assert verify_forgot_resp.status_code == 200
        assert "access_token" in verify_forgot_resp.json()
        assert verify_forgot_resp.json()["role"] == "patient"
        print("[OK] Admin request, approval, rejection, deletion, and forgot password verification successful")

        print("\n=== ALL TESTS PASSED SUCCESSFULLY ===")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Unexpected error in test run: {e}")
        raise
    finally:
        teardown_module()

if __name__ == "__main__":
    test_healthcare_backend()
