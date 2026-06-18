import os
import shutil
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup test DB
os.environ["DATABASE_URL"] = "sqlite:///./test_chats.db"
os.environ["SECRET_KEY"] = "test_secret_key_12345"

from app.main import app
from app.database import Base, get_db

engine = create_engine("sqlite:///./test_chats.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def setup_teardown():
    # Setup tables
    Base.metadata.create_all(bind=engine)
    
    # Setup uploads folder
    base_dir = os.path.dirname(os.path.abspath(__file__))
    uploads_dir = os.path.join(base_dir, "uploads")
    if os.path.exists(uploads_dir):
        shutil.rmtree(uploads_dir)
    os.makedirs(uploads_dir, exist_ok=True)
    
    yield
    
    # Teardown
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("test_chats.db"):
        try:
            os.remove("test_chats.db")
        except Exception as e:
            print(f"Could not remove test_chats.db: {e}")
    if os.path.exists(uploads_dir):
        shutil.rmtree(uploads_dir)

def test_chats_and_notifications_flow():
    # 1. Register a doctor and a patient
    doc_res = client.post("/auth/register", json={
        "email": "testdoc@example.com",
        "password": "Password123!",
        "role": "doctor"
    })
    print("DOC REGISTER RESPONSE:", doc_res.status_code, doc_res.text)
    assert doc_res.status_code == 201
    
    pat_res = client.post("/auth/register", json={
        "email": "testpat@example.com",
        "password": "Password123!",
        "role": "patient"
    })
    assert pat_res.status_code == 201

    # Verify patient OTP
    db = TestingSessionLocal()
    pat_user = db.query(models_import().User).filter_by(email="testpat@example.com").first()
    pat_otp = pat_user.otp
    doc_user = db.query(models_import().User).filter_by(email="testdoc@example.com").first()
    doc_otp = doc_user.otp
    db.close()
    
    pat_verify = client.post("/auth/verify-otp", json={
        "email": "testpat@example.com",
        "otp": pat_otp
    })
    assert pat_verify.status_code == 200
    pat_token = pat_verify.json()["access_token"]
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    doc_verify = client.post("/auth/verify-otp", json={
        "email": "testdoc@example.com",
        "otp": doc_otp
    })
    assert doc_verify.status_code == 200
    doc_token = doc_verify.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # 2. Get contacts for patient (should see doctors and admins)
    contacts_res = client.get("/chats/contacts", headers=pat_headers)
    assert contacts_res.status_code == 200
    # Patient should see doctors (doc verification status must be verified first)
    db = TestingSessionLocal()
    # verify doctor manually in db
    from app.models import Doctor, DoctorVerification
    doc_model = db.query(Doctor).filter_by(user_id=doc_user.id).first()
    if not doc_model:
        doc_model = Doctor(user_id=doc_user.id, name="Dr. Test", specialization="General Medicine", experience_years=5, location="Room A", contact="testdoc@example.com", license_number="LIC123")
        db.add(doc_model)
        db.flush()
    ver = DoctorVerification(doctor_id=doc_model.id, status="verified")
    db.add(ver)
    db.commit()
    db.close()

    contacts_res = client.get("/chats/contacts", headers=pat_headers)
    assert contacts_res.status_code == 200
    contacts = contacts_res.json()
    assert len(contacts) > 0
    assert any(c["id"] == doc_user.id for c in contacts)

    # 3. Patient starts conversation with Doctor
    start_conv = client.post("/chats/conversations/start", json={"target_user_id": doc_user.id}, headers=pat_headers)
    assert start_conv.status_code == 200
    conv_id = start_conv.json()["id"]

    # 4. Patient sends text message to Doctor
    send_msg = client.post(
        f"/chats/conversations/{conv_id}/send",
        data={"content": "Hello Dr. Test, here is my feedback!"},
        headers=pat_headers
    )
    assert send_msg.status_code == 200
    assert send_msg.json()["content"] == "Hello Dr. Test, here is my feedback!"

    # 5. Doctor checks notifications
    notifs_res = client.get("/chats/notifications", headers=doc_headers)
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()
    assert len(notifs) == 1
    assert "New message" in notifs[0]["message"]
    notif_id = notifs[0]["id"]

    # 6. Doctor marks notification as read
    read_res = client.post(f"/chats/notifications/{notif_id}/read", headers=doc_headers)
    assert read_res.status_code == 200
    
    # Check notifications again (should be empty)
    notifs_res_after = client.get("/chats/notifications", headers=doc_headers)
    assert len(notifs_res_after.json()) == 0

    # 7. Doctor sends a reply message with file attachment
    import io
    file_data = ("prescription.pdf", io.BytesIO(b"dummy prescription data"))
    send_reply = client.post(
        f"/chats/conversations/{conv_id}/send",
        data={"content": "Take this prescription twice a day."},
        files={"file": file_data},
        headers={**doc_headers}
    )
    assert send_reply.status_code == 200
    assert send_reply.json()["attachment_name"] == "prescription.pdf"
    assert "/uploads/" in send_reply.json()["attachment_path"]

    # 8. Test Switch Role for admin approved user
    # Try to switch role when has_admin_permission is False
    switch_fail = client.post("/auth/switch-role", headers=pat_headers)
    assert switch_fail.status_code == 403 # forbidden
    
    # Approve admin permissions for patient
    db = TestingSessionLocal()
    pat_db_user = db.query(models_import().User).filter_by(id=pat_user.id).first()
    pat_db_user.has_admin_permission = True
    db.commit()
    db.close()

    # Now switch role (should switch from patient to admin)
    switch_ok = client.post("/auth/switch-role", headers=pat_headers)
    assert switch_ok.status_code == 200
    assert switch_ok.json()["role"] == "admin"

    # Switch back (should switch from admin to patient)
    switch_back = client.post("/auth/switch-role", headers=pat_headers)
    assert switch_back.status_code == 200
    assert switch_back.json()["role"] == "patient"

def models_import():
    from app import models
    return models

if __name__ == "__main__":
    import sys
    print("Setting up test database...")
    generator = setup_teardown()
    next(generator)
    try:
        print("Running tests...")
        test_chats_and_notifications_flow()
        print("SUCCESS: All tests passed!")
    except Exception as e:
        print(f"FAILURE: Test failed due to error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            next(generator)
        except StopIteration:
            pass
