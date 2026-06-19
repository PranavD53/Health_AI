import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app.models import User, TriageCase

from sqlalchemy.pool import StaticPool

# Use a separate test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Override get_current_user to bypass auth
from app.routes.auth import get_current_user
def override_get_current_user():
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "testpatient@healthai.com").first()
    if not user:
        user = User(email="testpatient@healthai.com", password="dummy", role="patient")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def override_get_current_doctor():
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "testdoc@healthai.com").first()
    if not user:
        user = User(email="testdoc@healthai.com", password="dummy", role="doctor")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_new_features.db"):
        os.remove("./test_new_features.db")

def test_symptom_triage_emergency():
    app.dependency_overrides[get_current_user] = override_get_current_user
    response = client.post("/chat/symptom", json={"message": "I am having severe chest pain and can't breathe."})
    assert response.status_code == 200
    data = response.json()
    assert data["is_emergency"] is True
    assert "108" in data["response"] or "emergency" in data["response"].lower()

def test_symptom_triage_mild():
    app.dependency_overrides[get_current_user] = override_get_current_user
    # Mock call_llm because Groq might fail or take time in CI
    # We will let it hit Groq, if Groq fails it uses the fallback/dummy in llm_client
    response = client.post("/chat/symptom", json={"message": "I have a mild runny nose and minor ache."})
    assert response.status_code == 200
    data = response.json()
    # It might be an emergency if the LLM hallucinated, but it shouldn't be.
    assert data["is_emergency"] is False
    assert "case_id" in data

def test_doctor_override():
    # Create a case first
    db = TestingSessionLocal()
    user = override_get_current_user()
    case = TriageCase(patient_id=user.id, ai_severity="MODERATE", status="PENDING_REVIEW")
    db.add(case)
    db.commit()
    db.refresh(case)
    
    app.dependency_overrides[get_current_user] = override_get_current_doctor
    response = client.patch(f"/chat/symptom/doctor/{case.id}", json={
        "doctor_final_severity": "SEVERE",
        "doctor_notes": "Patient needs immediate checkup"
    })
    
    assert response.status_code == 200
    
    # Verify in DB
    db.expire_all()
    updated_case = db.query(TriageCase).filter(TriageCase.id == case.id).first()
    assert updated_case.doctor_final_severity == "SEVERE"
    assert updated_case.doctor_notes == "Patient needs immediate checkup"

def test_lab_report_unsupported():
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    # Create a dummy PDF file that has no marker keywords
    import reportlab.pdfgen.canvas as canvas
    import io
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)
    c.drawString(100, 750, "Random document about allergies that has enough text to pass.")
    c.drawString(100, 730, "This is an extra line so that the text extraction sees more.")
    c.drawString(100, 710, "This ensures it doesn't fail the minimum length check for pdfplumber.")
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    
    response = client.post(
        "/chat/lab-report/upload", 
        files={"file": ("dummy.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "currently supported" in data["response"]

def test_lab_report_supported_cbc():
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    import reportlab.pdfgen.canvas as canvas
    import io
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer)
    c.drawString(100, 750, "CBC Test Results")
    c.drawString(100, 730, "Hemoglobin: 11.0")  # Should be flagged LOW
    c.drawString(100, 710, "WBC: 6.0") # Normal
    c.drawString(100, 690, "Platelet Count: 200.0") # Normal
    c.drawString(100, 670, "Hematocrit: 40.0")
    c.save()
    pdf_bytes = pdf_buffer.getvalue()
    
    response = client.post(
        "/chat/lab-report/upload", 
        files={"file": ("cbc_test.pdf", pdf_bytes, "application/pdf")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["test_type"] == "CBC"
    assert "Hemoglobin" in data["flags"]
    assert data["flags"]["Hemoglobin"] == "LOW"
    assert "WBC" not in data["flags"]

def test_lab_report_bad_file():
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    response = client.post(
        "/chat/lab-report/upload", 
        files={"file": ("bad_file.txt", b"just some text without pdf structure", "text/plain")}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "Unable to read this report clearly" in data["response"]

