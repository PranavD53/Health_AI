import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from app.database import engine, Base, get_db
from app import models
from app.routes import auth, profile, symptoms, doctors, appointments, records, dashboard, chats
from app.routes.auth import get_current_user, require_role, log_action
from app.routes.auth import get_password_hash
from app.routes.doctors import seed_doctors
from app.routes.symptoms import scan_for_emergency

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, "Frontend")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")

if not os.path.exists(UPLOADS_DIR):
    os.makedirs(UPLOADS_DIR)

app = FastAPI(
    title="AI Healthcare Assistant",
    description="Backend API for managing user profiles, medical records, appointments, symptoms analysis, and AI chat capabilities.",
    version="1.0.0"
)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def run_migrations():
    from sqlalchemy import text
    db_url = os.getenv("DATABASE_URL", "")
    is_sqlite = "sqlite" in db_url or not db_url
    
    migrations = [
        # users
        ("users", "otp", "VARCHAR"),
        ("users", "is_verified", "BOOLEAN DEFAULT FALSE"),
        ("users", "admin_requested", "BOOLEAN DEFAULT FALSE"),
        ("users", "has_admin_permission", "BOOLEAN DEFAULT FALSE"),
        ("users", "base_role", "VARCHAR DEFAULT 'patient'"),
        # patient_profiles
        ("patient_profiles", "address", "TEXT"),
        ("patient_profiles", "profile_picture", "VARCHAR"),
        # doctors
        ("doctors", "address", "TEXT"),
        ("doctors", "profile_picture", "VARCHAR"),
        ("doctors", "license_document_path", "VARCHAR"),
        ("doctors", "license_number", "VARCHAR"),
        ("doctors", "user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL" if not is_sqlite else "INTEGER"),
        # medical_records
        ("medical_records", "fraud_status", "VARCHAR DEFAULT 'VERIFIED (Authentic)'"),
    ]

    print("Running database migrations for existing tables...")
    try:
        with engine.begin() as conn:
            for table, col, col_type in migrations:
                try:
                    if is_sqlite:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type};"))
                        print(f"Migration: Added column {col} to {table} (SQLite)")
                    else:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                        print(f"Migration: Ensured column {col} exists in {table} (Postgres)")
                except Exception as e:
                    # Ignore errors (column probably already exists)
                    pass
    except Exception as e:
        print(f"Migration error: {e}")

# --- Startup Event to Initialize and Seed DB ---
@app.on_event("startup")
def startup_db_setup():
    # Run migrations to verify database schema matches model updates
    run_migrations()
    # Automatically create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    # Seed the doctors table
    db = next(get_db())
    try:
        seed_doctors(db)
        seed_demo_users(db)
    finally:
        db.close()


def seed_demo_users(db: Session):
    demo_users = [
        ("patient@healthai.test", "patient", "Password123!"),
        ("alice.smith@hospital.com", "doctor", "Password123!"),
        ("admin@healthai.test", "admin", "Password123!"),
        ("sricharanpranav1@gmail.com", "admin", "Pranav@123"),
    ]

    for email, role, password in demo_users:
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user:
            user = existing_user
            if role == "admin":
                user.has_admin_permission = True
                user.base_role = "admin"
                db.commit()
        else:
            user = models.User(
                email=email,
                password=get_password_hash(password),
                role=role,
                base_role=role,
                has_admin_permission=True if role == "admin" else False,
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        if role == "patient":
            existing_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == user.id).first()
            if not existing_profile:
                profile = models.PatientProfile(
                    user_id=user.id,
                    name="Sarah Johnson",
                    date_of_birth="1994-04-18",
                    gender="Female",
                    height=165,
                    weight=62,
                    allergies="Pollen",
                    existing_conditions="None reported",
                )
                db.add(profile)
                db.commit()

            # Seed Patient Metrics
            metric_checks = ["heart_rate", "sleep", "steps"]
            metric_defaults = {"heart_rate": "72", "sleep": "7h 45m", "steps": "8,432"}
            for m_type in metric_checks:
                existing_metric = db.query(models.PatientMetric).filter(
                    models.PatientMetric.user_id == user.id,
                    models.PatientMetric.metric_type == m_type
                ).first()
                if not existing_metric:
                    metric = models.PatientMetric(
                        user_id=user.id,
                        metric_type=m_type,
                        value=metric_defaults[m_type]
                    )
                    db.add(metric)
            db.commit()

        elif role == "doctor":
            # Link doctor user with the seeded doctor record matching email contact
            seeded_doctor = db.query(models.Doctor).filter(models.Doctor.contact == "alice.smith@hospital.com").first()
            if seeded_doctor:
                seeded_doctor.user_id = user.id
                db.commit()

    # Seed Doctor Verifications for verification queue
    all_doctors = db.query(models.Doctor).all()
    for doc in all_doctors:
        existing_verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doc.id).first()
        if not existing_verification:
            # Let Dr. Evan Wright be pending verification, and the others verified
            status = "pending" if "Evan" in doc.name else "verified"
            verification = models.DoctorVerification(
                doctor_id=doc.id,
                status=status
            )
            db.add(verification)
    db.commit()

# --- Include Routers ---
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(symptoms.router)
app.include_router(doctors.router)
app.include_router(appointments.router)
app.include_router(records.router)
app.include_router(dashboard.router)
app.include_router(chats.router)


@app.get("/", include_in_schema=False)
def open_frontend():
    return RedirectResponse(url="/frontend/unified_login_flow/code.html")

# --- Pydantic Schemas for Conversations & AI & Notifications ---
class ConversationCreate(BaseModel):
    title: Optional[str] = None

class ConversationResponse(BaseModel):
    id: int
    user_id: int
    title: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]

class AIChatInput(BaseModel):
    message: str

class AISymptomInput(BaseModel):
    symptoms: str
    duration: str
    severity: str

class AIResponse(BaseModel):
    reply: str
    emergency_detected: bool
    disclaimer: str

class NotificationSend(BaseModel):
    recipient_id: int
    message: str
    alert_type: str = "general" # emergency, general, reminder

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    details: Optional[str]
    timestamp: datetime.datetime

    class Config:
        from_attributes = True
# --- Dynamic Dashboard & Metrics Schemas ---
class PatientMetricsResponse(BaseModel):
    heart_rate: str
    sleep: str
    steps: str

class MetricLog(BaseModel):
    metric_type: str
    value: str

class DoctorAppointmentInfo(BaseModel):
    id: int
    patient_name: str
    patient_gender: str
    patient_dob: str
    time: str
    date: str
    type: str
    priority: str
    status: str

class PatientSummaryInfo(BaseModel):
    user_id: int
    name: str
    gender: str
    date_of_birth: str
    allergies: str
    existing_conditions: str
    last_visit: str

class DoctorDashboardResponse(BaseModel):
    name: str
    specialization: str
    license_number: str
    consultations_count: int
    rating: float
    profile_completion: int
    verification_status: str
    upcoming_appointments: List[DoctorAppointmentInfo]
    patient_summaries: List[PatientSummaryInfo]

class VerificationQueueItem(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    specialization: str
    contact: str
    experience_years: int
    submitted_at: datetime.datetime
    status: str
    license_number: Optional[str] = None
    license_document_path: Optional[str] = None

class UserManagementInfo(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    admin_requested: bool = False

class AdminAppointmentInfo(BaseModel):
    id: int
    patient_id: int
    patient_email: str
    doctor_id: int
    doctor_name: str
    date: str
    time: str
    status: str

class AdminRecordInfo(BaseModel):
    id: int
    user_id: int
    patient_email: str
    file_name: str
    file_path: str
    file_type: str
    uploaded_at: datetime.datetime

class AdminDashboardResponse(BaseModel):
    total_patients: int
    total_doctors: int
    pending_verifications: int
    active_sessions: int
    verification_queue: List[VerificationQueueItem]
    audit_logs: List[AuditLogResponse]
    users: List[UserManagementInfo]
    appointments: List[AdminAppointmentInfo] = []
    records: List[AdminRecordInfo] = []

class VerifyDoctorRequest(BaseModel):
    status: str

# --- Dynamic Dashboard & Metrics Endpoints ---

@app.get("/dashboard/metrics", response_model=PatientMetricsResponse)
def get_patient_metrics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        hr = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "heart_rate").order_by(models.PatientMetric.recorded_at.desc()).first()
        sl = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "sleep").order_by(models.PatientMetric.recorded_at.desc()).first()
        st = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "steps").order_by(models.PatientMetric.recorded_at.desc()).first()
        return {
            "heart_rate": hr.value if hr else "72",
            "sleep": sl.value if sl else "7h 45m",
            "steps": st.value if st else "8432"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/dashboard/metrics")
def log_patient_metric(
    data: MetricLog,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        new_metric = models.PatientMetric(
            user_id=current_user.id,
            metric_type=data.metric_type,
            value=data.value
        )
        db.add(new_metric)
        db.commit()
        log_action(db, current_user.id, "LOG_METRIC", f"Logged metric {data.metric_type}: {data.value}")
        return {"status": "success", "message": f"{data.metric_type} logged successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/doctor/dashboard", response_model=DoctorDashboardResponse)
def get_doctor_dashboard(
    current_user: models.User = Depends(require_role(["doctor"])),
    db: Session = Depends(get_db)
):
    try:
        # Find doctor profile associated with current user
        doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if not doctor:
            doctor = db.query(models.Doctor).filter(models.Doctor.contact == current_user.email).first()
            if doctor:
                doctor.user_id = current_user.id
                db.commit()
                db.refresh(doctor)
            else:
                doctor = models.Doctor(
                    user_id=current_user.id,
                    name="Dr. " + (current_user.email.split("@")[0].title()),
                    specialization="General Medicine",
                    location="Suite 100, Medical Plaza",
                    experience_years=8,
                    available=True,
                    contact=current_user.email,
                    license_number="MD-DEMO-AI"
                )
                db.add(doctor)
                db.commit()
                db.refresh(doctor)

        # Get verification status
        verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doctor.id).first()
        verification_status = verification.status if verification else "verified" # default to verified if seeded

        # Upcoming appointments
        appointments = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == doctor.id,
            models.Appointment.status == "booked"
        ).order_by(models.Appointment.date.asc(), models.Appointment.time.asc()).all()

        upcoming = []
        for appt in appointments:
            p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == appt.patient_id).first()
            patient_name = p_profile.name if p_profile else "Unknown Patient"
            patient_gender = p_profile.gender if p_profile else "Unknown"
            patient_dob = p_profile.date_of_birth if p_profile else "Unknown"

            # Dynamic priority based on symptom log severity (if any)
            latest_symptom = db.query(models.SymptomLog).filter(models.SymptomLog.user_id == appt.patient_id).order_by(models.SymptomLog.created_at.desc()).first()
            priority = "Normal"
            appt_type = "Initial Consultation"
            if latest_symptom:
                if latest_symptom.severity.lower() == "severe":
                    priority = "High"
                elif latest_symptom.severity.lower() == "mild":
                    priority = "Low"
                appt_type = f"Follow-up ({latest_symptom.symptoms[:15]}...)"

            upcoming.append({
                "id": appt.id,
                "patient_name": patient_name,
                "patient_gender": patient_gender,
                "patient_dob": patient_dob,
                "time": appt.time,
                "date": appt.date,
                "type": appt_type,
                "priority": priority,
                "status": appt.status
            })

        # Patient summaries
        patient_ids = [a.patient_id for a in db.query(models.Appointment.patient_id).filter(models.Appointment.doctor_id == doctor.id).distinct().all()]
        patient_summaries = []
        for pid in patient_ids:
            p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == pid).first()
            if p_profile:
                last_appt = db.query(models.Appointment).filter(
                    models.Appointment.patient_id == pid,
                    models.Appointment.doctor_id == doctor.id
                ).order_by(models.Appointment.date.desc()).first()
                patient_summaries.append({
                    "user_id": pid,
                    "name": p_profile.name,
                    "gender": p_profile.gender or "Unknown",
                    "date_of_birth": p_profile.date_of_birth or "Unknown",
                    "allergies": p_profile.allergies or "None reported",
                    "existing_conditions": p_profile.existing_conditions or "None reported",
                    "last_visit": last_appt.date if last_appt else "N/A"
                })

        # Total consultations count
        consultations_count = db.query(models.Appointment).filter(models.Appointment.doctor_id == doctor.id).count()

        return {
            "name": doctor.name,
            "specialization": doctor.specialization,
            "license_number": doctor.license_number or f"MD-{doctor.id}00{doctor.experience_years}-AI",
            "consultations_count": consultations_count,
            "rating": 4.9,
            "profile_completion": 92,
            "verification_status": verification_status,
            "upcoming_appointments": upcoming,
            "patient_summaries": patient_summaries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/dashboard", response_model=AdminDashboardResponse)
def get_admin_dashboard(
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        total_patients = db.query(models.User).filter(models.User.role == "patient").count()
        total_doctors = db.query(models.Doctor).count()
        pending_verifications = db.query(models.DoctorVerification).filter(models.DoctorVerification.status == "pending").count()
        
        # Live audit logs for active sessions estimate
        recent_logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(50).all()
        active_sessions = 12 + len(recent_logs) # mock baseline + active log volume

        # Verification queue
        queue_items = db.query(models.DoctorVerification).filter(models.DoctorVerification.status == "pending").all()
        queue = []
        for item in queue_items:
            doc = db.query(models.Doctor).filter(models.Doctor.id == item.doctor_id).first()
            if doc:
                queue.append({
                    "id": item.id,
                    "doctor_id": doc.id,
                    "doctor_name": doc.name,
                    "specialization": doc.specialization,
                    "contact": doc.contact,
                    "experience_years": doc.experience_years,
                    "submitted_at": item.submitted_at,
                    "status": item.status,
                    "license_number": doc.license_number,
                    "license_document_path": doc.license_document_path
                })

        # Users list
        users_list = db.query(models.User).all()
        users = [{"id": u.id, "email": u.email, "role": u.role, "is_active": u.is_active, "admin_requested": u.admin_requested} for u in users_list]

        # Audit logs mapping to response model
        audit_logs_res = []
        for log in recent_logs[:15]:
            audit_logs_res.append({
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "details": log.details,
                "timestamp": log.timestamp
            })

        # Query all appointments for admin view
        appointments_list = db.query(models.Appointment).order_by(models.Appointment.date.desc(), models.Appointment.time.desc()).all()
        appointments = []
        for appt in appointments_list:
            patient = db.query(models.User).filter(models.User.id == appt.patient_id).first()
            doctor = db.query(models.Doctor).filter(models.Doctor.id == appt.doctor_id).first()
            appointments.append({
                "id": appt.id,
                "patient_id": appt.patient_id,
                "patient_email": patient.email if patient else "Unknown",
                "doctor_id": appt.doctor_id,
                "doctor_name": doctor.name if doctor else "Unknown",
                "date": appt.date,
                "time": appt.time,
                "status": appt.status
            })

        # Query all medical records for admin view
        records_list = db.query(models.MedicalRecord).order_by(models.MedicalRecord.uploaded_at.desc()).all()
        records = []
        for rec in records_list:
            patient = db.query(models.User).filter(models.User.id == rec.user_id).first()
            records.append({
                "id": rec.id,
                "user_id": rec.user_id,
                "patient_email": patient.email if patient else "Unknown",
                "file_name": rec.file_name,
                "file_path": rec.file_path,
                "file_type": rec.file_type,
                "uploaded_at": rec.uploaded_at
            })

        return {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "pending_verifications": pending_verifications,
            "active_sessions": active_sessions,
            "verification_queue": queue,
            "audit_logs": audit_logs_res,
            "users": users,
            "appointments": appointments,
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/verify-doctor/{id}")
def verify_doctor(
    id: int,
    data: VerifyDoctorRequest,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.id == id).first()
        if not verification:
            raise HTTPException(status_code=404, detail="Verification request not found")

        verification.status = data.status.lower()
        db.commit()

        # Update doctor availability based on verification
        doctor = db.query(models.Doctor).filter(models.Doctor.id == verification.doctor_id).first()
        if doctor:
            doctor.available = (data.status.lower() == "verified")
            db.commit()

        log_action(db, current_user.id, "VERIFY_DOCTOR", f"Doctor ID {verification.doctor_id} set to verification status: {data.status}")
        return {"status": "success", "message": f"Doctor verification status updated to {data.status}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- Conversations API ---

@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def start_conversation(
    conv_data: ConversationCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        title = conv_data.title or f"Chat on {datetime.date.today().strftime('%Y-%m-%d')}"
        new_conv = models.Conversation(
            user_id=current_user.id,
            title=title
        )
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)

        log_action(db, current_user.id, "START_CONVERSATION", f"Started conversation ID {new_conv.id}: '{title}'")
        return new_conv
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while starting conversation: {str(e)}"
        )

@app.get("/conversations", response_model=List[ConversationResponse])
def get_my_conversations(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        conversations = db.query(models.Conversation).filter(
            models.Conversation.user_id == current_user.id
        ).order_by(models.Conversation.created_at.desc()).all()
        return conversations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching conversations: {str(e)}"
        )

@app.get("/conversations/{id}", response_model=ConversationDetailResponse)
def get_one_conversation(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        conversation = db.query(models.Conversation).filter(models.Conversation.id == id).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        # RBAC Check: Users can view their own; Doctors/Admins/Caregivers can view any
        if current_user.role == "patient" and conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this conversation is forbidden"
            )

        messages = db.query(models.Message).filter(
            models.Message.conversation_id == id
        ).order_by(models.Message.timestamp.asc()).all()

        return {
            "conversation": conversation,
            "messages": messages
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching conversation details: {str(e)}"
        )

@app.post("/conversations/{id}/messages", response_model=MessageResponse)
async def send_message(
    id: int,
    msg_data: MessageCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        conversation = db.query(models.Conversation).filter(models.Conversation.id == id).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found"
            )

        if current_user.role == "patient" and conversation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden"
            )

        # 1. Save user's message
        user_message = models.Message(
            conversation_id=id,
            role="user",
            content=msg_data.content
        )
        db.add(user_message)
        db.commit()

        # 2. Check for emergency keywords
        is_emergency = scan_for_emergency(msg_data.content)
        disclaimer = "This is AI-generated information. Please consult a real doctor."

        if is_emergency:
            # If emergency, return standard prompt warning and call 108 suggestion
            assistant_content = (
                "EMERGENCY WARNING: The symptoms you described may require immediate medical attention. "
                "Please contact emergency services (call 108) or go to the nearest emergency room immediately."
            )
            # Log emergency event
            log_action(
                db, 
                current_user.id, 
                "EMERGENCY_DETECTED_IN_CHAT", 
                f"Emergency keywords flagged in Conversation {id}: '{msg_data.content}'"
            )
        else:
            # Load Groq API configurations
            groq_key = os.getenv("GROQ_API_KEY", "")
            has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")

            if has_valid_key:
                try:
                    # Retrieve conversation history
                    history_msgs = db.query(models.Message).filter(
                        models.Message.conversation_id == id
                    ).order_by(models.Message.timestamp.asc()).all()

                    payload_msgs = [
                        {
                            "role": "system",
                            "content": "You are a helpful medical assistant. Give general health information only. Always recommend consulting a doctor. Never diagnose or prescribe medication."
                        }
                    ]
                    # Append last 10 messages for context
                    for h_msg in history_msgs[-10:]:
                        payload_msgs.append({"role": h_msg.role, "content": h_msg.content})

                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {groq_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "llama-3.1-8b-instant",
                                "messages": payload_msgs,
                                "temperature": 0.5
                            },
                            timeout=8.0
                        )

                        if response.status_code == 200:
                            res_json = response.json()
                            assistant_content = res_json["choices"][0]["message"]["content"].strip()
                        else:
                            raise Exception(f"Groq API returned status {response.status_code}")
                except Exception as e:
                    print(f"Groq Chat API Error: {e}")
                    assistant_content = "I am sorry, but I am unable to connect to the medical knowledge base right now. Please try again shortly."
            else:
                assistant_content = (
                    "Thank you for sharing. For general wellness: keep a balanced diet, stay physically active, and monitor your symptoms. "
                    "Since my AI interface is operating in offline mode, I cannot provide custom insights."
                )

            # Append the mandatory disclaimer
            assistant_content = f"{assistant_content}\n\n[Disclaimer: {disclaimer}]"

        # 3. Save assistant's message
        assistant_message = models.Message(
            conversation_id=id,
            role="assistant",
            content=assistant_content
        )
        db.add(assistant_message)
        db.commit()
        db.refresh(assistant_message)

        return assistant_message
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while sending message: {str(e)}"
        )

class AIAssistantInput(BaseModel):
    message: str
    groq_key: Optional[str] = None
    hf_key: Optional[str] = None

class AIAssistantResponse(BaseModel):
    reply: str
    action: Optional[dict] = None
    disclaimer: str

@app.post("/ai/assistant", response_model=AIAssistantResponse)
async def global_ai_assistant(
    input_data: AIAssistantInput,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import re
    import json
    try:
        is_emergency = scan_for_emergency(input_data.message)
        disclaimer = "This is AI-generated information. Please consult a real doctor."

        if is_emergency:
            reply = (
                "EMERGENCY WARNING: Severe symptoms detected. Please call 108 or head to "
                "the nearest emergency department immediately."
            )
            return {
                "reply": reply,
                "action": None,
                "disclaimer": disclaimer
            }

        # Find or create a dedicated global assistant conversation thread
        conv = db.query(models.Conversation).filter(
            models.Conversation.user_id == current_user.id,
            models.Conversation.title == "HealthAI Global Assistant"
        ).first()

        if not conv:
            conv = models.Conversation(
                user_id=current_user.id,
                title="HealthAI Global Assistant"
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        # Save user message
        user_msg = models.Message(
            conversation_id=conv.id,
            role="user",
            content=input_data.message
        )
        db.add(user_msg)
        db.commit()

        # Load history (last 8 messages)
        history_msgs = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).order_by(models.Message.timestamp.asc()).all()

        user_context = (
            f"CURRENT USER CONTEXT:\n"
            f"- Logged-in User Email: {current_user.email}\n"
            f"- Role: {current_user.role}\n"
        )
        if current_user.role == "doctor":
            user_context += (
                "IMPORTANT ROLE CONSTRAINT: The user you are talking to is registered as a DOCTOR. "
                "Doctors do NOT seek other doctors or book appointments for themselves. "
                "Instead, their dashboard (/dashboard) contains their patient directory, queue, and upcoming consultations. "
                "If they ask to see their appointments, schedule, or consultations, guide them to their dashboard and trigger the 'view_dashboard' action. "
                "Do NOT recommend consulting other specialists or scheduling bookings for them unless they explicitly ask to consult another doctor as a patient.\n"
            )
        elif current_user.role == "admin":
            user_context += (
                "IMPORTANT ROLE CONSTRAINT: The user you are talking to is an ADMINISTRATOR. "
                "If they ask for system logs, stats, or configurations, guide them to their dashboard (/dashboard) and trigger the 'view_dashboard' action.\n"
            )
        else:
            user_context += (
                "IMPORTANT ROLE CONSTRAINT: The user you are talking to is a PATIENT. "
                "Patients can search for doctors (find_doctors), book appointments (book_appointment), and upload medical records (view_records).\n"
            )

        messages_payload = [
            {
                "role": "system",
                "content": (
                    "You are the HealthAI Global Assistant, a compassionate, precise, and highly fluent multilingual AI healthcare assistant.\n\n"
                    f"{user_context}\n"
                    "LANGUAGE PROTOCOL:\n"
                    "- If the user communicates in English, you MUST respond in pure, standard English. Do NOT mix Hindi, Hinglish, or Telugu words.\n"
                    "- If the user communicates in Hindi (हिन्दी), respond in Hindi.\n"
                    "- If the user communicates in Telugu (తెలుగు), respond in Telugu.\n"
                    "- Only respond in Hinglish (e.g., 'Aapka appointment book ho gaya hai') if the user explicitly typed their message in Hinglish.\n"
                    "- Only respond in Telugu-transliterated (e.g., 'Me appointment book ayyindi') if the user explicitly typed their message in Telugu-transliterated.\n"
                    "- Automatically detect and align with the user's input language style. Never default to Hinglish or transliterated styles for plain English queries.\n\n"
                    "CRITICAL RESPONSE LENGTH CONSTRAINT:\n"
                    "You MUST provide extremely concise, short, direct, and helpful answers (maximum 2-3 sentences, 40-50 words max). "
                    "Do NOT write long paragraphs. Get straight to the point and do not drag the conversation.\n\n"
                    "You can perform actions on behalf of the user by appending a special JSON block to the END of your response.\n"
                    "For example, if you decide to execute an action, output EXACTLY like this:\n"
                    "[ACTION: {\"type\": \"ACTION_TYPE\", \"parameters\": { ... }}]\n\n"
                    "Available actions:\n"
                    "1. Find Doctors:\n"
                    "   type: \"find_doctors\"\n"
                    "   parameters: {\"specialization\": \"cardiology\" | \"dermatology\" | \"general\" | \"neurology\" | \"pediatrics\"}\n"
                    "   Trigger this when the user asks to search for doctors, find a clinic, or look for a medical specialist.\n\n"
                    "2. Book Appointment:\n"
                    "   type: \"book_appointment\"\n"
                    "   parameters: {\"doctor_id\": int, \"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\"}\n"
                    "   Trigger this when the user wants to book, schedule, or reserve an appointment.\n"
                    "   CRITICAL: Before booking, you MUST explicitly ask for and receive the following details from the user:\n"
                    "   - Doctor's name or specialization\n"
                    "   - Date for the appointment\n"
                    "   - Preferred time\n"
                    "   Only output the booking action block AFTER the user has provided all three details. Do not book with defaults.\n"
                    "   If any detail is missing, ask for it first before proceeding with the booking.\n"
                    "   (Available Doctors: ID 1: Dr. Alice Smith, ID 2: Dr. Bob Johnson, ID 3: Dr. Charlie Brown, ID 4: Dr. Diana Prince, ID 5: Dr. Evan Wright)\n\n"
                    "3. View Medical Records:\n"
                    "   type: \"view_records\"\n"
                    "   parameters: {}\n"
                    "   Trigger this when the user wants to see their uploaded medical files, reports, or records.\n\n"
                    "4. Analyze Symptoms:\n"
                    "   type: \"analyze_symptom\"\n"
                    "   parameters: {\"symptoms\": \"description of symptoms\", \"severity\": \"mild\" | \"moderate\" | \"severe\", \"duration\": \"duration description\"}\n"
                    "   Trigger this when the user wants to check symptoms or get a health assessment.\n\n"
                    "5. View Dashboard:\n"
                    "   type: \"view_dashboard\"\n"
                    "   parameters: {}\n"
                    "   Trigger this when the user asks to go home, view overview, or see their dashboard.\n\n"
                    "6. Lodge a Complaint:\n"
                    "   type: \"lodge_complaint\"\n"
                    "   parameters: {\"message\": \"description of complaint/issue\"}\n"
                    "   Trigger this when the user complains about the system, service, doctors, or submits negative feedback.\n\n"
                    "7. View Settings:\n"
                    "   type: \"view_settings\"\n"
                    "   parameters: {}\n"
                    "   Trigger this when the user wants to update their profile, username, address, preferences, or settings.\n\n"
                    "8. View Chat Workspace:\n"
                    "   type: \"view_chat\"\n"
                    "   parameters: {}\n"
                    "   Trigger this when the user wants to message, chat, send a prescription/file, or chat with a doctor, patient, or admin.\n\n"
                    "9. Clinical Symptom Analysis & Doctor Mapping:\n"
                    "   If the user lists their symptoms (even in broken, informal, or transliterated languages, e.g. 'mere chest me pain ho raha hai' or 'talanoppiga vundi'):\n"
                    "   a) Diagnose/recommend the correct specialist to consult from our list:\n"
                    "      - Dr. Alice Smith (Cardiology, ID 1) for chest pain, heart, BP, palpitations, or shortness of breath.\n"
                    "      - Dr. Bob Johnson (Dermatology, ID 2) for skin rashes, itching, acne, hair fall, or eczema.\n"
                    "      - Dr. Charlie Brown (General Medicine, ID 3) for cold, cough, mild fever, minor stomach aches, or general symptoms.\n"
                    "      - Dr. Diana Prince (Neurology, ID 4) for headaches, migraines, nerve pain, dizziness, or seizures.\n"
                    "      - Dr. Evan Wright (Pediatrics, ID 5) for child health or pediatric vaccines.\n"
                    "   b) Safe OTC Medicine Recommendation:\n"
                    "      For minor, simple, non-critical symptoms (e.g. mild fever, common cold, minor headache, acid reflux), you may suggest a standard safe over-the-counter medicine (e.g., Paracetamol for mild fever, Cetirizine for cold/allergies, Antacids for indigestion) with clear dosage guidelines. You MUST append a safety disclaimer: 'This is general advice. Please consult a doctor if symptoms persist or worsen.'\n"
                    "   c) For critical or severe symptoms (e.g. severe chest pressure, unconsciousness, severe bleeding), advise them to seek emergency care immediately (dial 108/100).\n"
                    "   d) Proactively offer to schedule a consultation with the matched doctor (e.g. 'Would you like to book an appointment with our specialist Dr. Alice Smith?') and collect their preferred date and time step-by-step before triggering the booking action.\n\n"
                    "Always prioritize safety, give clear advice in their language, and include the action JSON block if the user's intent matches one of the actions."
                )
            }
        ]

        for h_msg in history_msgs[-8:]:
            messages_payload.append({"role": h_msg.role, "content": h_msg.content})

        # Use provided keys from request or fall back to environment variables
        groq_key = input_data.groq_key or os.getenv("GROQ_API_KEY", "")
        hf_key = input_data.hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))
        
        has_groq = groq_key and not groq_key.startswith("your_groq_api_key")
        has_hf = hf_key and not hf_key.startswith("your_hf_api_key")

        reply = ""

        if has_groq:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {groq_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.1-8b-instant",
                            "messages": messages_payload,
                            "temperature": 0.3
                        },
                        timeout=8.0
                    )
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"].strip()
                    else:
                        raise Exception(f"Groq API status: {response.status_code}")
            except Exception as e:
                print(f"Groq error: {e}")

        if not reply and has_hf:
            try:
                # Use Llama-3.2-3B-Instruct via Hugging Face Serverless API
                async with httpx.AsyncClient() as client:
                    prompt = ""
                    for msg in messages_payload:
                        role_tag = "<|system|>" if msg["role"] == "system" else "<|user|>" if msg["role"] == "user" else "<|assistant|>"
                        prompt += f"{role_tag}\n{msg['content']}\n"
                    prompt += "<|assistant|>\n"

                    response = await client.post(
                        "https://api-inference.huggingface.co/models/meta-llama/Llama-3.2-3B-Instruct",
                        headers={
                            "Authorization": f"Bearer {hf_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "inputs": prompt,
                            "parameters": {"max_new_tokens": 250, "temperature": 0.3}
                        },
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        res_json = response.json()
                        if isinstance(res_json, list) and len(res_json) > 0:
                            generated = res_json[0].get("generated_text", "")
                            if "<|assistant|>" in generated:
                                reply = generated.split("<|assistant|>")[-1].strip()
                            else:
                                reply = generated.replace(prompt, "").strip()
            except Exception as e:
                print(f"Hugging Face error: {e}")

        if not reply:
            # Offline rule-based fallback
            msg_lower = input_data.message.lower()
            
            # Check if user is in booking flow (either started now or was recently active)
            history_user_texts = [m.content.lower() for m in history_msgs if m.role == "user" and m.content]
            history_assistant_texts = [m.content.lower() for m in history_msgs if m.role == "assistant" and m.content]
            all_user_texts = " ".join(history_user_texts) + " " + msg_lower
            
            is_booking_intent = any(k in msg_lower for k in ["book", "schedule", "appointment", "appointment Book", "अपॉइंटमेंट", "అపాయింట్మెంట్"])
            was_booking_prompted = any(any(k in txt for k in ["book", "appointment", "doctor", "prefer", "time"]) for txt in history_assistant_texts[-3:])
            
            in_booking_flow = is_booking_intent or was_booking_prompted
            
            if in_booking_flow:
                # 1. Extract Doctor
                selected_doc_id = None
                selected_doc_name = None
                
                if any(k in all_user_texts for k in ["alice", "smith", "cardiology", "cardiologist", "एलिस", "స్మిత్"]):
                    selected_doc_id = 1
                    selected_doc_name = "Dr. Alice Smith"
                elif any(k in all_user_texts for k in ["bob", "johnson", "dermatology", "dermatologist", "बॉब", "జాన్సన్"]):
                    selected_doc_id = 2
                    selected_doc_name = "Dr. Bob Johnson"
                elif any(k in all_user_texts for k in ["charlie", "brown", "general medicine", "general physician", "चार्लि", "బ్రౌన్"]):
                    selected_doc_id = 3
                    selected_doc_name = "Dr. Charlie Brown"
                elif any(k in all_user_texts for k in ["diana", "prince", "neurology", "neurologist", "डायना", "ప్రిన్స్"]):
                    selected_doc_id = 4
                    selected_doc_name = "Dr. Diana Prince"
                elif any(k in all_user_texts for k in ["evan", "wright", "pediatrics", "pediatrician", "child", "एवन", "రైట్"]):
                    selected_doc_id = 5
                    selected_doc_name = "Dr. Evan Wright"
                
                # 2. Extract Date
                from datetime import datetime, timedelta
                selected_date = None
                
                # Check for explicit YYYY-MM-DD pattern
                date_match = re.search(r'\b(202\d-\d{2}-\d{2})\b', all_user_texts)
                if date_match:
                    selected_date = date_match.group(1)
                elif "tomorrow" in all_user_texts or "कल" in all_user_texts or "రేపు" in all_user_texts:
                    selected_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                elif "today" in all_user_texts or "आज" in all_user_texts or "ఈ రోజు" in all_user_texts:
                    selected_date = datetime.now().strftime("%Y-%m-%d")
                else:
                    days_mapping = {
                        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                        "friday": 4, "saturday": 5, "sunday": 6
                    }
                    for day, day_num in days_mapping.items():
                        if day in all_user_texts:
                            today = datetime.now()
                            days_ahead = day_num - today.weekday()
                            if days_ahead <= 0:
                                days_ahead += 7
                            selected_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                            break
                
                # 3. Extract Time
                selected_time = None
                time_match = re.search(r'\b(\d{1,2}:\d{2})\b', all_user_texts)
                if time_match:
                    t_str = time_match.group(1)
                    if len(t_str.split(':')[0]) == 1:
                        t_str = "0" + t_str
                    selected_time = t_str
                elif any(k in all_user_texts for k in ["morning", "सुबह", "ఉదయం"]):
                    selected_time = "10:00"
                elif any(k in all_user_texts for k in ["afternoon", "दोपहर", "మధ్యాహ్నం"]):
                    selected_time = "14:00"
                elif any(k in all_user_texts for k in ["evening", "शाम", "సాయంత్రం"]):
                    selected_time = "17:00"
                else:
                    am_pm_match = re.search(r'\b(\d{1,2})\s*(am|pm)\b', all_user_texts)
                    if am_pm_match:
                        hour = int(am_pm_match.group(1))
                        period = am_pm_match.group(2)
                        if period == "pm" and hour < 12:
                            hour += 12
                        elif period == "am" and hour == 12:
                            hour = 0
                        selected_time = f"{hour:02d}:00"
                
                # 4. Formulate conversational response
                if not selected_doc_id:
                    reply = (
                        "To book an appointment, please choose a doctor:\n"
                        "- Dr. Alice Smith (Cardiology)\n"
                        "- Dr. Bob Johnson (Dermatology)\n"
                        "- Dr. Charlie Brown (General Medicine)\n"
                        "- Dr. Diana Prince (Neurology)\n"
                        "- Dr. Evan Wright (Pediatrics)\n\n"
                        "Which doctor or specialization would you like to consult?"
                    )
                elif not selected_date:
                    reply = (
                        f"I've selected {selected_doc_name}. "
                        "What date would you prefer? (e.g., 'today', 'tomorrow', 'this Friday', or a date like YYYY-MM-DD)"
                    )
                elif not selected_time:
                    reply = (
                        f"I have scheduled {selected_doc_name} for {selected_date}. "
                        "What time would you prefer? (e.g., 'morning', 'afternoon', or a specific time like 10:00 AM)"
                    )
                else:
                    reply = (
                        f"I have successfully booked an appointment with {selected_doc_name} on {selected_date} at {selected_time}."
                        f"\n\n[ACTION: {{\"type\": \"book_appointment\", \"parameters\": {{\"doctor_id\": {selected_doc_id}, \"date\": \"{selected_date}\", \"time\": \"{selected_time}\"}}}}]"
                    )
            elif "doctor" in msg_lower or "specialist" in msg_lower or "clinic" in msg_lower:
                reply = "Sure, I can help you search for doctors. Please check the doctor search results.\n\n[ACTION: {\"type\": \"find_doctors\", \"parameters\": {\"specialization\": \"general\"}}]"
            elif "record" in msg_lower or "file" in msg_lower or "report" in msg_lower:
                reply = "I've pulled up your medical records directory. You can view or upload files there.\n\n[ACTION: {\"type\": \"view_records\", \"parameters\": {}}]"
            elif "symptom" in msg_lower or "pain" in msg_lower or "check" in msg_lower or "sick" in msg_lower or "hurt" in msg_lower or "fever" in msg_lower or "cold" in msg_lower or "cough" in msg_lower or "headache" in msg_lower or "migraine" in msg_lower or "rash" in msg_lower or "acne" in msg_lower:
                doc_recommendation = ""
                otc_recommendation = ""
                spec = "general"
                
                if any(k in msg_lower for k in ["chest", "heart", "bp", "cardio", "breath"]):
                    doc_recommendation = "Dr. Alice Smith (Cardiology, ID 1)"
                    otc_recommendation = "Please avoid self-medication for cardiovascular issues. Rest and consult a doctor immediately."
                    spec = "cardiology"
                elif any(k in msg_lower for k in ["skin", "rash", "acne", "itch", "eczema", "hair"]):
                    doc_recommendation = "Dr. Bob Johnson (Dermatology, ID 2)"
                    otc_recommendation = "For mild skin itching, apply Calamine lotion or take Cetirizine (10mg) daily."
                    spec = "dermatology"
                elif any(k in msg_lower for k in ["child", "kid", "baby", "pediatric", "vaccine"]):
                    doc_recommendation = "Dr. Evan Wright (Pediatrics, ID 5)"
                    otc_recommendation = "Pediatric dosages depend strictly on age and weight. Please consult a doctor."
                    spec = "pediatrics"
                elif any(k in msg_lower for k in ["headache", "migraine", "dizzy", "brain", "nerve", "head"]):
                    doc_recommendation = "Dr. Diana Prince (Neurology, ID 4)"
                    otc_recommendation = "For mild headaches, you can take a standard Paracetamol (500mg) tablet after meals."
                    spec = "neurology"
                else:
                    doc_recommendation = "Dr. Charlie Brown (General Medicine, ID 3)"
                    otc_recommendation = "For mild cold, cough or fever, a Paracetamol (500mg) or Cetirizine (10mg) after meals is suitable."
                    spec = "general"
                
                reply = (
                    f"I recommend consulting our specialist, {doc_recommendation}. "
                    f"{otc_recommendation} (Disclaimer: This is general advice. Please consult a doctor if symptoms persist.)\n\n"
                    f"[ACTION: {{\"type\": \"find_doctors\", \"parameters\": {{\"specialization\": \"{spec}\"}}}}]"
                )
            elif "setting" in msg_lower or "profile" in msg_lower or "address" in msg_lower or "username" in msg_lower:
                reply = "Opening your settings page where you can update your profile details and settings.\n\n[ACTION: {\"type\": \"view_settings\", \"parameters\": {}}]"
            elif "chat" in msg_lower or "message" in msg_lower or "conversation" in msg_lower or "inbox" in msg_lower:
                reply = "Opening your Chat Workspace so you can message and share files.\n\n[ACTION: {\"type\": \"view_chat\", \"parameters\": {}}]"
            elif "complaint" in msg_lower or "complain" in msg_lower or "feedback" in msg_lower:
                escaped_msg = input_data.message.replace('"', '\\"')
                reply = f"I've noted your complaint and forwarded it to our admin team. We will look into this immediately.\n\n[ACTION: {{\"type\": \"lodge_complaint\", \"parameters\": {{\"message\": \"{escaped_msg}\"}}}}]"
            else:
                reply = "I am the HealthAI Global Assistant. I can help you find doctors, book appointments, view your medical records, or analyze symptoms. How can I help you today?"

        # Parse action if present
        action = None
        action_match = re.search(r'\[ACTION:\s*(\{.*?\})\s*\]', reply, re.DOTALL)
        if action_match:
            try:
                parsed_action = json.loads(action_match.group(1))
                if parsed_action.get("type") == "book_appointment":
                    # Check recent conversation history user messages for doctor, date, and time
                    user_texts = " ".join([m.content.lower() for m in history_msgs if m.role == "user" and m.content])
                    user_texts += " " + input_data.message.lower()
                    
                    doc_keywords = ["smith", "johnson", "brown", "prince", "wright", "cardiology", "dermatology", "medicine", "neurology", "pediatrics", "doctor", "specialist", "डॉक्टर", "विशेषज्ञ", "డాక్టర్", "వైద్యుడు"]
                    date_keywords = ["tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "202", "date", "/", "कल", "आज", "तारीख", "दिनांक", "రేపు", "ఈ రోజు", "తేదీ"]
                    time_keywords = ["am", "pm", "morning", "afternoon", "evening", "o'clock", ":", "time", "बजे", "समय", "सुबह", "शाम", "दोपहर", "గంటల", "సమయం"]
                    
                    has_doctor = any(d in user_texts for d in doc_keywords)
                    has_date = any(d in user_texts for d in date_keywords)
                    has_time = any(t in user_texts for t in time_keywords)
                    
                    if not (has_doctor and has_date and has_time):
                        action = None
                        user_query = input_data.message
                        detected_lang = "en"
                        if any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in user_query):
                            detected_lang = "hi"
                        elif any(ord(c) >= 0x0C00 and ord(c) <= 0x0C7F for c in user_query):
                            detected_lang = "te"
                            
                        if detected_lang == "hi":
                            reply = "अपॉइंटमेंट बुक करने के लिए, मुझे कुछ और विवरण चाहिए। आप किस डॉक्टर से मिलना चाहते हैं, और किस तारीख और समय पर?"
                        elif detected_lang == "te":
                            reply = "అపాయింట్‌మెంట్ బుక్ చేయడానికి, నాకు మరికొన్ని వివరాలు కావాలి. మీరు ఏ వైద్యుడిని సంప్రదించాలనుకుంటున్నారు, మరియు ఏ తేదీ మరియు సమయంలో?"
                        else:
                            reply = "To book your appointment, I need a few more details. Which doctor or specialization would you like to consult, and on what date and time?"
                    else:
                        action = parsed_action
                        reply = reply.replace(action_match.group(0), "").strip()
                else:
                    action = parsed_action
                    reply = reply.replace(action_match.group(0), "").strip()
            except Exception as ex:
                print(f"Action parse error: {ex}")

        # Save assistant reply
        assistant_msg = models.Message(
            conversation_id=conv.id,
            role="assistant",
            content=f"{reply}\n\n[Disclaimer: {disclaimer}]"
        )
        db.add(assistant_msg)
        db.commit()

        return {
            "reply": reply,
            "action": action,
            "disclaimer": disclaimer
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assistant error: {str(e)}"
        )

# --- AI Assistant API (Ad-Hoc) ---

@app.post("/ai/chat", response_model=AIResponse)
async def ai_chat(
    input_data: AIChatInput,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        is_emergency = scan_for_emergency(input_data.message)
        disclaimer = "This is AI-generated information. Please consult a real doctor."

        if is_emergency:
            reply = (
                "EMERGENCY ALERT: It seems you may be experiencing a medical emergency. "
                "Do not wait. Please call emergency services (108) or visit the nearest hospital emergency department immediately."
            )
            log_action(
                db, 
                current_user.id, 
                "EMERGENCY_DETECTED_IN_CHAT", 
                f"Ad-hoc chat emergency keywords: '{input_data.message}'"
            )
            return {
                "reply": reply,
                "emergency_detected": True,
                "disclaimer": disclaimer
            }

        groq_key = os.getenv("GROQ_API_KEY", "")
        has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")

        if has_valid_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {groq_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.1-8b-instant",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a helpful medical assistant. Give general health information only. Always recommend consulting a doctor. Never diagnose or prescribe medication."
                                },
                                {
                                    "role": "user",
                                    "content": input_data.message
                                }
                            ],
                            "temperature": 0.5
                        },
                        timeout=8.0
                    )
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"].strip()
                    else:
                        raise Exception(f"Groq responded with status {response.status_code}")
            except Exception as e:
                print(f"Groq API error in ad-hoc chat: {e}")
                reply = "I cannot provide dynamic information right now. Please seek advice from a licensed medical professional."
        else:
            reply = "I am currently offline. Please consult a physician for any physical symptoms or health concerns."

        reply = f"{reply}\n\n[Disclaimer: {disclaimer}]"
        return {
            "reply": reply,
            "emergency_detected": False,
            "disclaimer": disclaimer
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during AI chat: {str(e)}"
        )

@app.post("/ai/symptom-check", response_model=AIResponse)
async def ai_symptom_check(
    input_data: AISymptomInput,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        combined_symptoms = f"{input_data.symptoms} (severity: {input_data.severity}, duration: {input_data.duration})"
        is_emergency = scan_for_emergency(combined_symptoms)
        disclaimer = "This is AI-generated information. Please consult a real doctor."

        if is_emergency:
            reply = (
                "EMERGENCY WARNING: Critical symptoms identified. Please contact medical emergency services (call 108) "
                "or head to the emergency room immediately."
            )
            log_action(
                db, 
                current_user.id, 
                "EMERGENCY_DETECTED_IN_SYMPTOM_CHECK", 
                f"Ad-hoc symptom check emergency: '{combined_symptoms}'"
            )
            return {
                "reply": reply,
                "emergency_detected": True,
                "disclaimer": disclaimer
            }

        groq_key = os.getenv("GROQ_API_KEY", "")
        has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")

        if has_valid_key:
            try:
                async with httpx.AsyncClient() as client:
                    user_prompt = (
                        f"Please analyze these symptoms:\n"
                        f"Symptoms: {input_data.symptoms}\n"
                        f"Duration: {input_data.duration}\n"
                        f"Severity: {input_data.severity}\n\n"
                        f"Provide a brief assessment, potential general causes (not a definitive diagnosis), "
                        f"and recommended action plan (e.g. self-care vs scheduling a doctor visit)."
                    )
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {groq_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.1-8b-instant",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a helpful medical assistant. Give general health information only. Always recommend consulting a doctor. Never diagnose or prescribe medication."
                                },
                                {
                                    "role": "user",
                                    "content": user_prompt
                                }
                            ],
                            "temperature": 0.4
                        },
                        timeout=8.0
                    )
                    if response.status_code == 200:
                        reply = response.json()["choices"][0]["message"]["content"].strip()
                    else:
                        raise Exception(f"Groq API returned status {response.status_code}")
            except Exception as e:
                print(f"Groq API error in symptom check: {e}")
                reply = "Unable to process symptoms at the moment. Please consult a physician."
        else:
            reply = (
                f"You reported: '{input_data.symptoms}' with a severity of '{input_data.severity}' lasting for '{input_data.duration}'. "
                "We recommend resting and booking an appointment with a general practitioner for an accurate physical evaluation."
            )

        reply = f"{reply}\n\n[Disclaimer: {disclaimer}]"
        return {
            "reply": reply,
            "emergency_detected": False,
            "disclaimer": disclaimer
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during symptom check: {str(e)}"
        )

# --- Notifications API ---

@app.post("/notifications/send")
def send_notification(
    notification: NotificationSend,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check permissions: Caregivers, Doctors, and Admins can send to anyone. Patients can only send to themselves or caregivers.
        if current_user.role == "patient" and notification.recipient_id != current_user.id:
            # Query if recipient is a caregiver or if there is a caregiver-patient relationship
            # To keep it simple, block patients from sending to arbitrary IDs unless it's themselves.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to send notifications to this recipient."
            )

        # Log notification event
        log_action(
            db, 
            current_user.id, 
            "NOTIFICATION_SENT", 
            f"Notification of type '{notification.alert_type}' sent to User ID {notification.recipient_id}. Content: '{notification.message}'"
        )

        return {
            "status": "success",
            "message": f"Notification successfully sent to user ID {notification.recipient_id}",
            "details": {
                "alert_type": notification.alert_type,
                "sent_at": datetime.datetime.utcnow().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while sending notification: {str(e)}"
        )

# --- Audit Logs API (Admin Only) ---

@app.get("/audit/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        logs = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).all()
        return logs
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving audit logs: {str(e)}"
        )

# --- Emergency Alerts Schemas and Endpoints ---

class EmergencyAlertResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_address: Optional[str] = None
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class ComplaintCreate(BaseModel):
    message: str

class ComplaintResponse(BaseModel):
    id: int
    user_id: int
    user_email: str
    message: str
    status: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@app.post("/emergency/sos", response_model=EmergencyAlertResponse)
def trigger_sos(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        patient_name = profile.name if profile else current_user.email
        patient_address = profile.address if (profile and profile.address) else "No address provided"

        alert = models.EmergencyAlert(
            patient_id=current_user.id,
            patient_name=patient_name,
            patient_address=patient_address,
            status="active"
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        log_action(db, current_user.id, "EMERGENCY_SOS_TRIGGERED", f"SOS triggered by {patient_name}. Address: {patient_address}")
        return alert
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emergency/alerts", response_model=List[EmergencyAlertResponse])
def get_emergency_alerts(
    current_user: models.User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    try:
        alerts = db.query(models.EmergencyAlert).filter(models.EmergencyAlert.status == "active").all()
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/emergency/resolve/{id}")
def resolve_emergency(
    id: int,
    current_user: models.User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    try:
        alert = db.query(models.EmergencyAlert).filter(models.EmergencyAlert.id == id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        alert.status = "resolved"
        db.commit()
        log_action(db, current_user.id, "EMERGENCY_SOS_RESOLVED", f"SOS Alert {id} resolved by {current_user.email}")
        return {"status": "success", "message": "Emergency alert marked as resolved"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai/complaint", response_model=ComplaintResponse)
def submit_complaint(
    data: ComplaintCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        complaint = models.Complaint(
            user_id=current_user.id,
            user_email=current_user.email,
            message=data.message,
            status="pending"
        )
        db.add(complaint)
        db.flush()
        
        # Notify admins
        admins = db.query(models.User).filter(models.User.role == "admin", models.User.is_active == True).all()
        for admin in admins:
            notif = models.Notification(
                user_id=admin.id,
                message=f"New complaint from {current_user.email}: {data.message[:35]}...",
                notification_type="complaint_submitted",
                related_id=complaint.id
            )
            db.add(notif)
            
        db.commit()
        db.refresh(complaint)
        log_action(db, current_user.id, "COMPLAINT_SUBMITTED", f"Complaint filed: {data.message[:50]}...")
        return complaint
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/complaints", response_model=List[ComplaintResponse])
def get_complaints(
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        complaints = db.query(models.Complaint).order_by(models.Complaint.created_at.desc()).all()
        return complaints
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/complaints/resolve/{id}")
def resolve_complaint(
    id: int,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        complaint = db.query(models.Complaint).filter(models.Complaint.id == id).first()
        if not complaint:
            raise HTTPException(status_code=404, detail="Complaint not found")
        complaint.status = "resolved"
        
        # Notify user
        notif = models.Notification(
            user_id=complaint.user_id,
            message="Your complaint has been resolved by Admin.",
            notification_type="complaint_resolved",
            related_id=complaint.id
        )
        db.add(notif)
        
        db.commit()
        log_action(db, current_user.id, "COMPLAINT_RESOLVED", f"Complaint ID {id} resolved by admin")
        return {"status": "success", "message": "Complaint marked as resolved"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
