import os
import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Header, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from app.database import engine, Base, get_db
from app.migrations import ensure_schema
from app import models
from app.routes import auth, profile, symptoms, doctors, appointments, records, dashboard, chats, calls, feedback, palettes
from app.routes.auth import get_current_user, require_role, log_action
from app.routes.auth import get_password_hash
from app.routes.doctors import seed_doctors
from app.routes.symptoms import scan_for_emergency

from app.config import BASE_DIR, UPLOADS_DIR, SYSTEM_CAPABILITIES

PROJECT_DIR = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_DIR, "Frontend")


# Restore seeded uploads on startup to recover from test wipes
SEED_UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
if os.path.exists(SEED_UPLOADS_DIR):
    import shutil
    for file_name in os.listdir(SEED_UPLOADS_DIR):
        src_file = os.path.join(SEED_UPLOADS_DIR, file_name)
        dst_file = os.path.join(UPLOADS_DIR, file_name)
        if os.path.isfile(src_file) and not os.path.exists(dst_file):
            try:
                shutil.copy2(src_file, dst_file)
            except Exception as e:
                print(f"Error restoring seeded upload {file_name}: {e}")

app = FastAPI(
    title="AI Healthcare Assistant",
    description="Backend API for managing user profiles, medical records, appointments, symptoms analysis, and AI chat capabilities.",
    version="1.0.0"
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Startup Event to Initialize and Seed DB ---
@app.on_event("startup")
def startup_db_setup():
    ensure_schema()
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
app.include_router(calls.router)
app.include_router(feedback.router)
app.include_router(palettes.router)


if os.path.isdir(FRONTEND_DIR):
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/", include_in_schema=False)
def open_frontend():
    return RedirectResponse(url="/frontend/unified_login_flow/code.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None), db: Session = Depends(get_db)):
    if not token:
        token = websocket.query_params.get("token")
        
    if not token:
        await websocket.close(code=1008)
        return

    try:
        from app.routes.auth import SECRET_KEY, ALGORITHM
        from jose import jwt, JWTError
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "access":
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not user.is_active:
        await websocket.close(code=1008)
        return

    from app.websocket_manager import manager
    await manager.connect(websocket, user.id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)

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
    total_patients: int
    today_appointments: List[DoctorAppointmentInfo]
    pending_appointments: int

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
    doctor_name: Optional[str] = None
    specialization: Optional[str] = None
    verification_status: Optional[str] = None
    verification_id: Optional[int] = None
    license_document_path: Optional[str] = None
    license_number: Optional[str] = None

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

        today_str = datetime.date.today().isoformat()
        today_appointments = [appt for appt in upcoming if appt["date"] == today_str]
        pending_appointments = len(upcoming)
        # Dynamic rating calculation
        feedbacks = db.query(models.Feedback).filter(
            models.Feedback.doctor_id == doctor.id,
            models.Feedback.is_approved == True
        ).all()
        avg_rating = 4.9
        if feedbacks:
            avg_rating = round(sum(f.rating_doctor for f in feedbacks) / len(feedbacks), 1)

        return {
            "name": doctor.name,
            "specialization": doctor.specialization,
            "license_number": doctor.license_number or f"MD-{doctor.id}00{doctor.experience_years}-AI",
            "consultations_count": consultations_count,
            "rating": avg_rating,
            "profile_completion": 92,
            "verification_status": verification_status,
            "upcoming_appointments": upcoming,
            "patient_summaries": patient_summaries,
            "total_patients": len(patient_summaries),
            "today_appointments": today_appointments,
            "pending_appointments": pending_appointments
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
        users = []
        for u in users_list:
            u_info = {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "is_active": u.is_active,
                "admin_requested": u.admin_requested,
                "doctor_name": None,
                "specialization": None,
                "verification_status": None,
                "verification_id": None,
                "license_document_path": None,
                "license_number": None
            }
            if u.role == "doctor":
                doc = db.query(models.Doctor).filter(models.Doctor.user_id == u.id).first()
                if doc:
                    u_info["doctor_name"] = doc.name
                    u_info["specialization"] = doc.specialization
                    u_info["license_document_path"] = doc.license_document_path
                    u_info["license_number"] = doc.license_number
                    verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doc.id).first()
                    if verification:
                        u_info["verification_status"] = verification.status
                        u_info["verification_id"] = verification.id
                    else:
                        u_info["verification_status"] = "pending"
            users.append(u_info)

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
            # Fallback: check if id is doctor_id
            verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == id).first()
            
        if not verification:
            # Create a pending one on the fly if doctor exists
            doctor = db.query(models.Doctor).filter(models.Doctor.id == id).first()
            if not doctor:
                # Or find doctor by user_id
                doctor = db.query(models.Doctor).filter(models.Doctor.user_id == id).first()
            if not doctor:
                raise HTTPException(status_code=404, detail="Verification request or Doctor not found")
            verification = models.DoctorVerification(doctor_id=doctor.id, status="pending")
            db.add(verification)
            db.commit()
            db.refresh(verification)

        verification.status = data.status.lower()
        db.commit()

        # Update doctor availability based on verification
        doctor = db.query(models.Doctor).filter(models.Doctor.id == verification.doctor_id).first()
        if doctor:
            doctor.available = (data.status.lower() == "verified")
            db.commit()

        log_action(db, current_user.id, "VERIFY_DOCTOR", f"Doctor ID {verification.doctor_id} set to verification status: {data.status}")
        return {"status": "success", "message": f"Doctor verification status updated to {data.status}", "verification_id": verification.id}
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
                            "content": (
                                "You are TARS, a helpful clinical AI medical assistant. Enforce these language rules:\n"
                                "1. If the user writes/speaks in English, respond strictly in English.\n"
                                "2. If the user writes/speaks in Hindi or Hinglish, respond in Hindi or Hinglish.\n"
                                "3. If the user writes/speaks in Telugu or Tinglish, respond in Telugu or Tinglish.\n"
                                "Always respond in the exact same language or language style/mix that the user used. "
                                "You can draw insights from symptom reports and medical records to suggest safe over-the-counter medications and care plans, accompanied by a safety warning. "
                                "Keep response text concise, fluid, and natural for Text-to-Speech (TTS) voice engines. Do not use tables, lists of special symbols, or formatting that sounds awkward when spoken."
                            )
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
    language: Optional[str] = None

class AIAssistantResponse(BaseModel):
    reply: str
    action: Optional[dict] = None
    disclaimer: str

class UIConfirmationInput(BaseModel):
    message: str
    groq_key: Optional[str] = None
    hf_key: Optional[str] = None

@app.get("/ai/config")
def get_ai_config(current_user: models.User = Depends(get_current_user)):
    return SYSTEM_CAPABILITIES

@app.post("/ai/evaluate_confirmation")
async def evaluate_confirmation(
    input_data: UIConfirmationInput,
    current_user: models.User = Depends(get_current_user)
):
    import json
    import httpx
    message_clean = input_data.message.strip().lower()
    
    # 1. Quick local check fallback first for standard english / local terms
    affirmative_tokens = {"yes", "yeah", "yep", "y", "confirm", "proceed", "okay", "ok", "sure", "do it", "haan", "ha", "ji", "avunu", "sare", "sari", "yes please", "correct"}
    negative_tokens = {"no", "nope", "n", "cancel", "stop", "dont", "don't", "reject", "deny", "nah", "nahi", "na", "vaddu", "oddu", "no thanks", "incorrect"}
    
    if message_clean in affirmative_tokens:
        return {"intent": "affirmative"}
    if message_clean in negative_tokens:
        return {"intent": "negative"}
        
    # 2. LLM dynamic parsing for natural speech in other languages
    groq_key = input_data.groq_key or os.getenv("GROQ_API_KEY", "")
    hf_key = input_data.hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))
    
    has_groq = groq_key and not groq_key.startswith("your_groq_api_key")
    has_hf = hf_key and not hf_key.startswith("your_hf_api_key")
    
    messages_payload = [
        {
            "role": "system",
            "content": (
                "You are a confirmation parser. Determine if the user's message represents an agreement/confirmation, a disagreement/cancellation, or if it is ambiguous.\n"
                "Classify the intent into one of:\n"
                "- 'affirmative' (agreement, yes, proceed, correct, confirm, haan, avunu, etc.)\n"
                "- 'negative' (disagreement, no, cancel, stop, vaddu, nahi, etc.)\n"
                "- 'ambiguous' (anything else)\n\n"
                "Output ONLY a raw JSON block with 'intent' key. Example:\n"
                "{\"intent\": \"affirmative\"}"
            )
        },
        {"role": "user", "content": f"User message: \"{input_data.message}\""}
    ]
    
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
                        "temperature": 0.0,
                        "max_tokens": 30
                    },
                    timeout=5.0
                )
                if response.status_code == 200:
                    res_json = response.json()
                    content_res = res_json["choices"][0]["message"]["content"].strip()
                    import re
                    match = re.search(r'\{.*?\}', content_res)
                    if match:
                        parsed = json.loads(match.group(0))
                        if parsed.get("intent") in ["affirmative", "negative", "ambiguous"]:
                            return {"intent": parsed["intent"]}
        except Exception:
            pass
            
    if has_hf:
        try:
            async with httpx.AsyncClient() as client:
                prompt = ""
                for msg in messages_payload:
                    role_tag = "<|system|>" if msg["role"] == "system" else "<|user|>"
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
                        "parameters": {"max_new_tokens": 30, "temperature": 0.0}
                    },
                    timeout=5.0
                )
                if response.status_code == 200:
                    res_json = response.json()
                    generated = ""
                    if isinstance(res_json, list) and len(res_json) > 0:
                        generated = res_json[0].get("generated_text", "")
                    content_res = generated.split("<|assistant|>")[-1].strip() if "<|assistant|>" in generated else generated
                    import re
                    match = re.search(r'\{.*?\}', content_res)
                    if match:
                        parsed = json.loads(match.group(0))
                        if parsed.get("intent") in ["affirmative", "negative", "ambiguous"]:
                            return {"intent": parsed["intent"]}
        except Exception:
            pass
            
    # Substring search check fallback
    for aff in ["yes", "yeah", "yep", "confirm", "proceed", "ok", "haan", "ha", "avunu", "sare", "sari", "correct"]:
        if aff in message_clean:
            return {"intent": "affirmative"}
    for neg in ["no", "nope", "cancel", "stop", "dont", "don't", "reject", "nah", "nahi", "na", "vaddu", "oddu"]:
        if neg in message_clean:
            return {"intent": "negative"}
            
    return {"intent": "ambiguous"}

@app.post("/ai/assistant")
async def global_ai_assistant(
    input_data: AIAssistantInput,
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    async def generate():
        import re
        import json
    
        # Determine language preference and detect language style dynamically
        current_msg = input_data.message.strip()
        pref_lang = "en"
        if input_data.language:
            pref_lang = input_data.language.split("-")[0].strip().lower()
        elif accept_language:
            pref_lang = accept_language.split(",")[0].split("-")[0].strip().lower()

        language_rule = (
            "Detect the user's input language and writing style (e.g., English, Hindi, Telugu, Spanish, Hinglish, Tinglish, etc.) from their query. "
            "Respond naturally in the EXACT SAME language, writing script, and style. "
            "If the user uses a transliterated language (like Hinglish or Tinglish), respond in that transliterated style. "
            "Ensure you do not translate to English unless requested; maintain alignment with the user's language."
        )
        
        try:
            is_emergency = scan_for_emergency(input_data.message)
            disclaimer = "This is AI-generated information. Please consult a real doctor."

            if is_emergency:
                reply = (
                    "EMERGENCY WARNING: Severe symptoms detected. Please call 108 or head to "
                    "the nearest emergency department immediately."
                )
                import json
                yield f"data: {json.dumps({'type': 'action', 'action': None, 'disclaimer': disclaimer, 'reply': reply})}\n\n"
                return

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

            # Fetch current date and time dynamically
            import datetime
            today_date = datetime.date.today()
            today_str = today_date.strftime("%Y-%m-%d")
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
            # Load active/verified doctors directory dynamically
            doctors_query = db.query(models.Doctor).all()
            # Create doctors directory string for LLM mapping (do NOT output IDs in text responses!)
            doctors_directory = "\n".join([f"- {doc.name} ({doc.specialization}, ID {doc.id})" for doc in doctors_query])

            user_context = (
                f"CURRENT DATE AND TIME: {current_time_str}\n"
                f"CURRENT USER CONTEXT:\n"
                f"- Logged-in User Email: {current_user.email}\n"
                f"- Role: {current_user.role}\n"
            )
        
            patient_appts = []
            doctor_appts = []
            doctor = None
        
            if current_user.role == "patient":
                # Query patient's upcoming appointments
                from sqlalchemy.orm import joinedload
                patient_appts = db.query(models.Appointment).options(
                    joinedload(models.Appointment.doctor)
                ).filter(
                    models.Appointment.patient_id == current_user.id,
                    models.Appointment.status == "booked"
                ).all()
                for appt in patient_appts:
                    _ = appt.doctor  # Force-load lazy relationship in-memory
                    try:
                        db.expunge(appt)
                    except Exception:
                        pass
                from app.routes.appointments import adjust_timestamps_generic
                adjust_timestamps_generic(patient_appts)
                patient_appts = [a for a in patient_appts if a.date >= today_str]
                patient_appts.sort(key=lambda x: (x.date, x.time))
            
                appts_list = []
                for appt in patient_appts:
                    doc_name = appt.doctor.name if appt.doctor else "Unknown Doctor"
                    doc_spec = appt.doctor.specialization if appt.doctor else "Specialist"
                    appts_list.append(f"- Appointment with {doc_name} ({doc_spec}) on {appt.date} at {appt.time}")
            
                if appts_list:
                    user_context += "YOUR UPCOMING APPOINTMENTS:\n" + "\n".join(appts_list) + "\n"
                else:
                    user_context += "YOUR UPCOMING APPOINTMENTS: You have no upcoming appointments scheduled.\n"
                
            elif current_user.role == "doctor":
                # Query doctor's profile and consultations
                doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
                if not doctor:
                    doctor = db.query(models.Doctor).filter(models.Doctor.contact == current_user.email).first()
            
                if doctor:
                    from sqlalchemy.orm import joinedload
                    doctor_appts = db.query(models.Appointment).options(
                        joinedload(models.Appointment.doctor)
                    ).filter(
                        models.Appointment.doctor_id == doctor.id,
                        models.Appointment.status == "booked"
                    ).all()
                    for appt in doctor_appts:
                        _ = appt.doctor  # Force-load lazy relationship in-memory
                        try:
                            db.expunge(appt)
                        except Exception:
                            pass
                    from app.routes.appointments import adjust_timestamps_generic
                    adjust_timestamps_generic(doctor_appts)
                    doctor_appts = [a for a in doctor_appts if a.date >= today_str]
                    doctor_appts.sort(key=lambda x: (x.date, x.time))
                
                    consults_list = []
                    for appt in doctor_appts:
                        p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == appt.patient_id).first()
                        p_name = p_profile.name if p_profile else "Unknown Patient"
                        consults_list.append(f"- Consultation with patient {p_name} on {appt.date} at {appt.time}")
                
                    if consults_list:
                        user_context += "YOUR UPCOMING CONSULTATIONS:\n" + "\n".join(consults_list) + "\n"
                    else:
                        user_context += "YOUR UPCOMING CONSULTATIONS: You have no upcoming consultations scheduled.\n"
                else:
                    user_context += "YOUR UPCOMING CONSULTATIONS: No doctor profile found.\n"

            if current_user.role == "doctor":
                user_context += (
                    "IMPORTANT ROLE CONSTRAINT: The user you are talking to is registered as a DOCTOR. "
                    "Doctors do NOT seek other doctors or book appointments for themselves. "
                    "If they ask to see their consultations, schedule, or appointments, read their upcoming consultations (patient name, date, time) to them directly. "
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

            # Get the allowed permissions for the user's role
            role_perms = SYSTEM_CAPABILITIES.get("roles", {}).get(current_user.role, {}).get("permissions", [])
            
            # Format the actions list dynamically based on permissions
            allowed_actions_list = []
            action_counter = 1
            for act_name, act_def in SYSTEM_CAPABILITIES.get("actions", {}).items():
                if act_name in role_perms:
                    desc = act_def.get("description", "")
                    params = act_def.get("parameters", {})
                    allowed_actions_list.append(
                        f"{action_counter}. {act_name.replace('_', ' ').title()}:" + chr(10) +
                        f"   type: \"{act_name}\"" + chr(10) +
                        f"   parameters: {json.dumps(params)}" + chr(10) +
                        f"   Trigger description: {desc}" + chr(10)
                    )
                    action_counter += 1
            allowed_actions_str = "".join(allowed_actions_list)

            messages_payload = [
                {
                    "role": "system",
                    "content": (
                        "You are TARS, a multilingual global assistant that offers medical and system assistance available on our website. You are compassionate, precise, and highly fluent." + chr(10) + chr(10) +
                        f"{user_context}" + chr(10) +
                        "LANGUAGE PROTOCOL:" + chr(10) +
                        f"- {language_rule}" + chr(10) +
                        "- Do NOT output or mention doctor IDs (e.g. 'ID 1', 'ID 2', etc.) in your conversational responses. " +
                        "When referring to a doctor, always refer to them by their name and department/specialization, e.g. 'Dr. Alice Smith (Cardiology)' or 'Dr. Bob Johnson (Dermatology)'. " +
                        "You MUST use the correct doctor ID in the JSON action block parameter 'doctor_id', but keep the IDs completely hidden from the user-facing text response." + chr(10) + chr(10) +
                        "CRITICAL RESPONSE LENGTH CONSTRAINT:" + chr(10) +
                        "You MUST provide extremely concise, short, direct, and helpful answers (maximum 2-3 sentences, 40-50 words max). " +
                        "Do NOT write long paragraphs. Get straight to the point and do not drag the conversation." + chr(10) + chr(10) +
                        "You can perform actions on behalf of the user by appending a special JSON block to the END of your response." + chr(10) +
                        "For example, if you decide to execute an action, output EXACTLY like this:" + chr(10) +
                        "[ACTION: {\"type\": \"ACTION_TYPE\", \"parameters\": { ... }}]" + chr(10) + chr(10) +
                        "Available actions for your role:" + chr(10) +
                        f"{allowed_actions_str}" + chr(10) + chr(10) +
                        "Always prioritize safety, give clear advice in their language, and include the action JSON block if the user's intent matches one of the actions."
                    )
                }
            ]

            for h_msg in history_msgs[-8:]:
                messages_payload.append({"role": h_msg.role, "content": h_msg.content})

            # Reinforce language rules directly on the last user message to override history bias
            if messages_payload and messages_payload[-1]["role"] == "user":
                prompt_instruction = (
                    chr(10) + chr(10) + f"[SYSTEM RULE: Detect the language script and style of the message above and respond strictly in the same script/style. "
                    f"Do NOT mention any doctor IDs in your response. Keep your response brief - maximum 2-3 sentences.]"
                )
                messages_payload[-1]["content"] += prompt_instruction

            # Use provided keys from request or fall back to environment variables
            groq_key = input_data.groq_key or os.getenv("GROQ_API_KEY", "")
            hf_key = input_data.hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))
        
            has_groq = groq_key and not groq_key.startswith("your_groq_api_key")
            has_hf = hf_key and not hf_key.startswith("your_hf_api_key")

            reply = ""

            if has_groq:
                try:
                    async with httpx.AsyncClient() as client:
                        async with client.stream(
                            "POST",
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={
                                "Authorization": f"Bearer {groq_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "llama-3.1-8b-instant",
                                "messages": messages_payload,
                                "temperature": 0.3,
                                "stream": True
                            },
                            timeout=8.0
                        ) as response:
                            if response.status_code == 200:
                                async for chunk in response.aiter_lines():
                                    if chunk.startswith("data: ") and chunk != "data: [DONE]":
                                        import json
                                        try:
                                            data_obj = json.loads(chunk[6:])
                                            content_chunk = data_obj["choices"][0]["delta"].get("content", "")
                                            if content_chunk:
                                                reply += content_chunk
                                                yield f"data: {json.dumps({'type': 'chunk', 'content': content_chunk})}\n\n"
                                        except Exception:
                                            pass
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
                            import json
                            yield f"data: {json.dumps({'type': 'chunk', 'content': reply})}\n\n"
                except Exception as e:
                    print(f"Hugging Face error: {e}")

            if not reply:
                # Offline rule-based fallback
                msg_lower = input_data.message.lower()
            
                # Check if user is asking about their own schedule/appointments/consultations
                is_schedule_query = any(k in msg_lower for k in ["show", "read", "view", "what", "my", "list", "check", "శెడ్యూల్", "అపాయింట్మెంట్", "షెడ్యూల్", "अपॉइंटमेंट", "शेड्यूल", "consultation", "consultations"]) and any(k in msg_lower for k in ["appointment", "appointments", "consultation", "consultations", "schedule", "visit", "visits", "meeting", "meetings", "record", "records"])
            
                # Check if user is in booking flow (either started now or was recently active)
                history_user_texts = [m.content.lower() for m in history_msgs if m.role == "user" and m.content]
                history_assistant_texts = [m.content.lower() for m in history_msgs if m.role == "assistant" and m.content]
                all_user_texts = " ".join(history_user_texts) + " " + msg_lower
            
                is_booking_intent = any(k in msg_lower for k in ["book", "schedule", "appointment", "appointment Book", "अपॉइंटमेंट", "అపాయింట్మెంట్"])
                was_booking_prompted = any(any(k in txt for k in ["book", "appointment", "doctor", "prefer", "time"]) for txt in history_assistant_texts[-3:])
            
                in_booking_flow = is_booking_intent or was_booking_prompted
            
                if is_schedule_query:
                    if current_user.role == "patient":
                        if patient_appts:
                            appts_txt = []
                            for appt in patient_appts:
                                doc_name = appt.doctor.name if appt.doctor else "Doctor"
                                doc_spec = appt.doctor.specialization if appt.doctor else "Specialist"
                                appts_txt.append(f"{doc_name} ({doc_spec}) on {appt.date} at {appt.time}")
                            appts_joined = ", ".join(appts_txt)
                            if pref_lang == "te":
                                reply = f"మీకు ఈ క్రింది రాబోయే అపాయింట్‌మెంట్‌లు ఉన్నాయి: {appts_joined}."
                            elif pref_lang == "hi":
                                reply = f"आपके पास निम्नलिखित आगामी अपॉइंटमेंट हैं: {appts_joined}."
                            else:
                                reply = f"You have the following upcoming appointments: {appts_joined}."
                        else:
                            if pref_lang == "te":
                                reply = "మీకు రాబోయే అపాయింట్‌మెంట్‌లు ఏవీ లేవు."
                            elif pref_lang == "hi":
                                reply = "आपके पास कोई आगामी अपॉइंटमेंट निर्धारित नहीं है।"
                            else:
                                reply = "You have no upcoming appointments scheduled."
                    elif current_user.role == "doctor":
                        if doctor and doctor_appts:
                            consults_txt = []
                            for appt in doctor_appts:
                                p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == appt.patient_id).first()
                                p_name = p_profile.name if p_profile else "Unknown Patient"
                                consults_txt.append(f"patient {p_name} on {appt.date} at {appt.time}")
                            consults_joined = ", ".join(consults_txt)
                            if pref_lang == "te":
                                reply = f"మీకు ఈ క్రింది రాబోయే సంప్రదింపులు ఉన్నాయి: {consults_joined}."
                            elif pref_lang == "hi":
                                reply = f"आपके पास निम्नलिखित आगामी परामर्श हैं: {consults_joined}."
                            else:
                                reply = f"You have the following upcoming consultations: {consults_joined}."
                        else:
                            if pref_lang == "te":
                                reply = "మీకు రాబోయే సంప్రదింపులు ఏవీ లేవు."
                            elif pref_lang == "hi":
                                reply = "आपके पास कोई आगामी परामर्श निर्धारित नहीं है।"
                            else:
                                reply = "You have no upcoming consultations scheduled."
                    else:
                        if pref_lang == "te":
                            reply = "అడ్మినిస్ట్రేటర్‌గా, మీకు అపాయింట్‌మెంట్‌లు లేదా సంప్రదింపులు లేవు."
                        elif pref_lang == "hi":
                            reply = "एक प्रशासक के रूप में, आपके पास कोई अपॉइंटमेंट या परामर्श नहीं है।"
                        else:
                            reply = "As an administrator, you do not have any appointments or consultations."
                        
                elif current_user.role in ["doctor", "admin"] and (in_booking_flow or any(k in msg_lower for k in ["appointment", "appointments", "doctor", "specialist"])):
                    if current_user.role == "doctor":
                        if pref_lang == "te":
                            reply = "మీరు ఒక రిజిస్టర్డ్ వైద్యునిగా అపాయింట్‌మెంట్‌లను బుక్ చేయలేరు లేదా బ్రౌజ్ చేయలేరు. మీరు మీ డాష్‌బోర్డ్ వర్క్‌స్పేస్ నుండి కన్సల్టేషన్‌లను నిర్వహించవచ్చు."
                        elif pref_lang == "hi":
                            reply = "आप एक पंजीकृत डॉक्टर के रूप में अपॉइंटमेंट बुक या ब्राउज़ नहीं कर सकते। आप अपने डैशबोर्ड कार्यक्षेत्र से परामर्श प्रबंधित करते हैं।"
                        else:
                            reply = "You cannot book or browse appointments as a registered doctor. You manage consultations from your dashboard workspace."
                    else:
                        if pref_lang == "te":
                            reply = "మీరు అడ్మినిస్ట్రేటర్‌గా అపాయింట్‌మెంట్‌లను బుక్ చేయలేరు లేదా బ్రౌజ్ చేయలేరు."
                        elif pref_lang == "hi":
                            reply = "आप एक प्रशासक के रूप में अपॉइंटमेंट बुक या ब्राउज़ नहीं कर सकते।"
                        else:
                            reply = "You cannot book or browse appointments as an administrator."
                        
                elif in_booking_flow:
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
                        if pref_lang == "te":
                            reply = (
                                "అపాయింట్‌మెంట్ బుక్ చేయడానికి, దయచేసి ఒక వైద్యుడిని ఎంచుకోండి:\n"
                                "- Dr. Alice Smith (కార్డియాలజీ)\n"
                                "- Dr. Bob Johnson (డెర్మటాలజీ)\n"
                                "- Dr. Charlie Brown (జనరల్ మెడిసిన్)\n"
                                "- Dr. Diana Prince (న్యూరాలజీ)\n"
                                "- Dr. Evan Wright (పీడియాట్రిక్స్)\n\n"
                                "మీరు ఏ వైద్యుడిని లేదా ఏ విభాగాన్ని సంప్రదించాలనుకుంటున్నారు?"
                            )
                        elif pref_lang == "hi":
                            reply = (
                                "अपॉइंटमेंट बुक करने के लिए, कृपया एक डॉक्टर चुनें:\n"
                                "- Dr. Alice Smith (हृदय रोग विशेषज्ञ)\n"
                                "- Dr. Bob Johnson (त्वचा विशेषज्ञ)\n"
                                "- Dr. Charlie Brown (सामान्य चिकित्सा)\n"
                                "- Dr. Diana Prince (न्यूरोलॉजिस्ट)\n"
                                "- Dr. Evan Wright (बाल रोग विशेषज्ञ)\n\n"
                                "आप किस डॉक्टर या विशेषज्ञ से परामर्श करना चाहते हैं?"
                            )
                        else:
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
                        if pref_lang == "te":
                            reply = (
                                f"నేను {selected_doc_name} ని ఎంచుకున్నాను. "
                                "మీరు ఏ తేదీని కోరుకుంటున్నారు? (ఉదాహరణకు, 'ఈ రోజు', 'రేపు', లేదా YYYY-MM-DD ఫార్మాట్‌లో తేదీ)"
                            )
                        elif pref_lang == "hi":
                            reply = (
                                f"मैंने {selected_doc_name} को चुना है। "
                                "आप किस तारीख को प्राथमिकता देंगे? (जैसे, 'आज', 'कल', या YYYY-MM-DD जैसी तारीख)"
                            )
                        else:
                            reply = (
                                f"I've selected {selected_doc_name}. "
                                "What date would you prefer? (e.g., 'today', 'tomorrow', 'this Friday', or a date like YYYY-MM-DD)"
                            )
                    elif not selected_time:
                        if pref_lang == "te":
                            reply = (
                                f"నేను {selected_doc_name} ని {selected_date} కోసం షెడ్యూల్ చేసాను. "
                                "మీరు ఏ సమయాన్ని కోరుకుంటున్నారు? (ఉదాహరణకు, 'ఉదయం', 'మధ్యాహ్నం', లేదా 10:00 AM వంటి సమయం)"
                            )
                        elif pref_lang == "hi":
                            reply = (
                                f"मैंने {selected_date} को {selected_doc_name} के लिए निर्धारित किया है। "
                                "आप किस समय को प्राथमिकता देंगे? (जैसे, 'सुबह', 'दोपहर', या 10:00 AM जैसा विशिष्ट समय)"
                            )
                        else:
                            reply = (
                                f"I have scheduled {selected_doc_name} for {selected_date}. "
                                "What time would you prefer? (e.g., 'morning', 'afternoon', or a specific time like 10:00 AM)"
                            )
                    else:
                        if pref_lang == "te":
                            reply = (
                                f"నేను {selected_doc_name} తో {selected_date} నాడు {selected_time} గంటలకు విజయవంతంగా అపాయింట్‌మెంట్ బుక్ చేసాను."
                                f"\n\n[ACTION: {{\"type\": \"book_appointment\", \"parameters\": {{\"doctor_id\": {selected_doc_id}, \"date\": \"{selected_date}\", \"time\": \"{selected_time}\"}}}}]"
                            )
                        elif pref_lang == "hi":
                            reply = (
                                f"मैंने {selected_date} को {selected_time} बजे {selected_doc_name} के साथ सफलतापूर्वक अपॉइंटमेंट बुक कर लिया है।"
                                f"\n\n[ACTION: {{\"type\": \"book_appointment\", \"parameters\": {{\"doctor_id\": {selected_doc_id}, \"date\": \"{selected_date}\", \"time\": \"{selected_time}\"}}}}]"
                            )
                        else:
                            reply = (
                                f"I have successfully booked an appointment with {selected_doc_name} on {selected_date} at {selected_time}."
                                f"\n\n[ACTION: {{\"type\": \"book_appointment\", \"parameters\": {{\"doctor_id\": {selected_doc_id}, \"date\": \"{selected_date}\", \"time\": \"{selected_time}\"}}}}]"
                            )
                elif "doctor" in msg_lower or "specialist" in msg_lower or "clinic" in msg_lower:
                    if pref_lang == "te":
                        reply = "ఖచ్చితంగా, నేను మీకు వైద్యులను వెతకడంలో సహాయపడగలను. దయచేసి ఫలితాలను చూడండి.\n\n[ACTION: {\"type\": \"find_doctors\", \"parameters\": {\"specialization\": \"general\"}}]"
                    elif pref_lang == "hi":
                        reply = "ज़रूर, मैं डॉक्टरों को खोजने में आपकी मदद कर सकता हूँ। कृपया खोज परिणाम देखें।\n\n[ACTION: {\"type\": \"find_doctors\", \"parameters\": {\"specialization\": \"general\"}}]"
                    else:
                        reply = "Sure, I can help you search for doctors. Please check the doctor search results.\n\n[ACTION: {\"type\": \"find_doctors\", \"parameters\": {\"specialization\": \"general\"}}]"
                elif "record" in msg_lower or "file" in msg_lower or "report" in msg_lower:
                    if pref_lang == "te":
                        reply = "నేను మీ వైద్య రికార్డుల డైరెక్టరీని తెరిచాను. మీరు అక్కడ ఫైళ్లను చూడవచ్చు లేదా అప్‌లోడ్ చేయవచ్చు.\n\n[ACTION: {\"type\": \"view_records\", \"parameters\": {}}]"
                    elif pref_lang == "hi":
                        reply = "मैंने आपकी मेडिकल रिकॉर्ड डायरेक्टरी खोल दी है। आप वहां फाइलें देख या अपलोड कर सकते हैं।\n\n[ACTION: {\"type\": \"view_records\", \"parameters\": {}}]"
                    else:
                        reply = "I've pulled up your medical records directory. You can view or upload files there.\n\n[ACTION: {\"type\": \"view_records\", \"parameters\": {}}]"
                elif "symptom" in msg_lower or "pain" in msg_lower or "check" in msg_lower or "sick" in msg_lower or "hurt" in msg_lower or "fever" in msg_lower or "cold" in msg_lower or "cough" in msg_lower or "headache" in msg_lower or "migraine" in msg_lower or "rash" in msg_lower or "acne" in msg_lower:
                    doc_recommendation = ""
                    otc_recommendation = ""
                    spec = "general"
                
                    if any(k in msg_lower for k in ["chest", "heart", "bp", "cardio", "breath"]):
                        if pref_lang == "te":
                            doc_recommendation = "Dr. Alice Smith (కార్డియాలజీ, ID 1)"
                            otc_recommendation = "హృదయ సంబంధిత సమస్యలకు దయచేసి స్వయం-మందులు తీసుకోకండి. విశ్రాంతి తీసుకోండి మరియు వెంటనే వైద్యుడిని సంప్రదించండి."
                        elif pref_lang == "hi":
                            doc_recommendation = "Dr. Alice Smith (हृदय रोग विशेषज्ञ, ID 1)"
                            otc_recommendation = "कृपया हृदय संबंधी समस्याओं के लिए स्व-दवा से बचें। आराम करें और तुरंत डॉक्टर से परामर्श लें।"
                        else:
                            doc_recommendation = "Dr. Alice Smith (Cardiology, ID 1)"
                            otc_recommendation = "Please avoid self-medication for cardiovascular issues. Rest and consult a doctor immediately."
                        spec = "cardiology"
                    elif any(k in msg_lower for k in ["skin", "rash", "acne", "itch", "eczema", "hair"]):
                        if pref_lang == "te":
                            doc_recommendation = "Dr. Bob Johnson (డెర్మటాలజీ, ID 2)"
                            otc_recommendation = "తేలికపాటి చర్మ దురద కోసం, కాలమైన్ లోషన్ రాయండి లేదా ప్రతిరోజూ సెటిరిజైన్ (10mg) తీసుకోండి."
                        elif pref_lang == "hi":
                            doc_recommendation = "Dr. Bob Johnson (त्वचा विशेषज्ञ, ID 2)"
                            otc_recommendation = "त्वचा की हल्की खुजली के लिए, कैलामाइन लोशन लगाएं या रोजाना Cetirizine (10mg) लें।"
                        else:
                            doc_recommendation = "Dr. Bob Johnson (Dermatology, ID 2)"
                            otc_recommendation = "For mild skin itching, apply Calamine lotion or take Cetirizine (10mg) daily."
                        spec = "dermatology"
                    elif any(k in msg_lower for k in ["child", "kid", "baby", "pediatric", "vaccine"]):
                        if pref_lang == "te":
                            doc_recommendation = "Dr. Evan Wright (పీడియాట్రిక్స్, ID 5)"
                            otc_recommendation = "పిల్లల మందుల మోతాదులు వారి వయస్సు మరియు బరువుపై ఆధారపడి ఉంటాయి. దయచేసి వైద్యుడిని సంప్రదించండి."
                        elif pref_lang == "hi":
                            doc_recommendation = "Dr. Evan Wright (बाल रोग विशेषज्ञ, ID 5)"
                            otc_recommendation = "बच्चों की दवा की खुराक पूरी तरह से उम्र और वजन पर निर्भर करती है। कृपया डॉक्टर से सलाह लें।"
                        else:
                            doc_recommendation = "Dr. Evan Wright (Pediatrics, ID 5)"
                            otc_recommendation = "Pediatric dosages depend strictly on age and weight. Please consult a doctor."
                        spec = "pediatrics"
                    elif any(k in msg_lower for k in ["headache", "migraine", "dizzy", "brain", "nerve", "head"]):
                        if pref_lang == "te":
                            doc_recommendation = "Dr. Diana Prince (న్యూరాలజీ, ID 4)"
                            otc_recommendation = "తేలికపాటి తలనొప్పి కోసం, భోజనం తర్వాత ఒక సాధారణ పారాసిటమాల్ (500mg) టాబ్లెట్ తీసుకోవచ్చు."
                        elif pref_lang == "hi":
                            doc_recommendation = "Dr. Diana Prince (न्यूरोलॉजिस्ट, ID 4)"
                            otc_recommendation = "हल्के सिरदर्द के लिए, आप भोजन के बाद एक मानक पैरासिटामोल (500mg) टैबलेट ले सकते हैं।"
                        else:
                            doc_recommendation = "Dr. Diana Prince (Neurology, ID 4)"
                            otc_recommendation = "For mild headaches, you can take a standard Paracetamol (500mg) tablet after meals."
                        spec = "neurology"
                    else:
                        if pref_lang == "te":
                            doc_recommendation = "Dr. Charlie Brown (జనరల్ మెడిసిన్, ID 3)"
                            otc_recommendation = "తేలికపాటి జలుబు, దగ్గు లేదా జ్వరం కోసం, భోజనం తర్వాత పారాసిటమాల్ (500mg) లేదా సెటిరిజైన్ (10mg) సరిపోతుంది."
                        elif pref_lang == "hi":
                            doc_recommendation = "Dr. Charlie Brown (सामान्य चिकित्सा, ID 3)"
                            otc_recommendation = "हल्की सर्दी, खांसी या बुखार के लिए, भोजन के बाद पैरासिटामोल (500mg) या Cetirizine (10mg) उपयुक्त है।"
                        else:
                            doc_recommendation = "Dr. Charlie Brown (General Medicine, ID 3)"
                            otc_recommendation = "For mild cold, cough or fever, a Paracetamol (500mg) or Cetirizine (10mg) after meals is suitable."
                        spec = "general"
                
                    if pref_lang == "te":
                        reply = (
                            f"నేను మా నిపుణుడు {doc_recommendation} ని సంప్రదించాలని సిఫార్సు చేస్తున్నాను. "
                            f"{otc_recommendation} (డిస్క్లైమర్: ఇది సాధారణ సలహా. లక్షణాలు తగ్గకపోతే దయచేసి వైద్యుడిని సంప్రదించండి.)\n\n"
                            f"[ACTION: {{\"type\": \"find_doctors\", \"parameters\": {{\"specialization\": \"{spec}\"}}}}]"
                        )
                    elif pref_lang == "hi":
                        reply = (
                            f"मैं हमारे विशेषज्ञ {doc_recommendation} से परामर्श करने की सलाह देता हूँ। "
                            f"{otc_recommendation} (अस्वीकरण: यह सामान्य सलाह है। यदि लक्षण बने रहते हैं तो कृपया डॉक्टर से परामर्श लें।)\n\n"
                            f"[ACTION: {{\"type\": \"find_doctors\", \"parameters\": {{\"specialization\": \"{spec}\"}}}}]"
                        )
                    else:
                        reply = (
                            f"I recommend consulting our specialist, {doc_recommendation}. "
                            f"{otc_recommendation} (Disclaimer: This is general advice. Please consult a doctor if symptoms persist.)\n\n"
                            f"[ACTION: {{\"type\": \"find_doctors\", \"parameters\": {{\"specialization\": \"{spec}\"}}}}]"
                        )
                elif "setting" in msg_lower or "profile" in msg_lower or "address" in msg_lower or "username" in msg_lower:
                    if pref_lang == "te":
                        reply = "మీ ప్రొఫైల్ వివరాలు మరియు సెట్టింగులను నవీకరించడానికి మీ సెట్టింగుల పేజీని తెరుస్తున్నాను.\n\n[ACTION: {\"type\": \"view_settings\", \"parameters\": {}}]"
                    elif pref_lang == "hi":
                        reply = "आपका सेटिंग्स पेज खोल रहा हूँ जहाँ आप अपनी प्रोफ़ाइल विवरण और सेटिंग्स अपडेट कर सकते हैं।\n\n[ACTION: {\"type\": \"view_settings\", \"parameters\": {}}]"
                    else:
                        reply = "Opening your settings page where you can update your profile details and settings.\n\n[ACTION: {\"type\": \"view_settings\", \"parameters\": {}}]"
                elif "chat" in msg_lower or "message" in msg_lower or "conversation" in msg_lower or "inbox" in msg_lower:
                    if pref_lang == "te":
                        reply = "సন্দేశాలు పంపడానికి మరియు ఫైళ్లను పంచుకోవడానికి మీ చాట్ వర్క్‌స్పేస్‌ను తెరుస్తున్నాను.\n\n[ACTION: {\"type\": \"view_chat\", \"parameters\": {}}]"
                    elif pref_lang == "hi":
                        reply = "आपका चैट वर्कस्पेस खोल रहा हूँ ताकि आप संदेश भेज सकें और फाइलें साझा कर सकें।\n\n[ACTION: {\"type\": \"view_chat\", \"parameters\": {}}]"
                    else:
                        reply = "Opening your Chat Workspace so you can message and share files.\n\n[ACTION: {\"type\": \"view_chat\", \"parameters\": {}}]"
                elif "complaint" in msg_lower or "complain" in msg_lower or "feedback" in msg_lower:
                    escaped_msg = input_data.message.replace('"', '\\"')
                    if pref_lang == "te":
                        reply = f"నేను మీ ఫిర్యాదును నమోదు చేసుకున్నాను మరియు మా అడ్మిన్ బృందానికి పంపించాను. మేము దీనిని వెంటనే పరిశీలిస్తాము.\n\n[ACTION: {{\"type\": \"lodge_complaint\", \"parameters\": {{\"message\": \"{escaped_msg}\"}}}}]"
                    elif pref_lang == "hi":
                        reply = f"मैंने आपकी शिकायत दर्ज कर ली है और इसे हमारी एडमिन टीम को भेज दिया है। हम इसे तुरंत देखेंगे।\n\n[ACTION: {{\"type\": \"lodge_complaint\", \"parameters\": {{\"message\": \"{escaped_msg}\"}}}}]"
                    else:
                        reply = f"I've noted your complaint and forwarded it to our admin team. We will look into this immediately.\n\n[ACTION: {{\"type\": \"lodge_complaint\", \"parameters\": {{\"message\": \"{escaped_msg}\"}}}}]"
                else:
                    if pref_lang == "te":
                        reply = "నేను హెల్త్AI గ్లోబల్ అసిస్టెంట్. నేను వైద్యులను కనుగొనడంలో, అపాయింట్‌మెంట్‌లను బుక్ చేయడంలో, వైద్య రికార్డులను చూపడంలో లేదా లక్షణాలను విశ్లేషించడంలో సహాయపడగలను. ఈ రోజు నేను మీకు ఎలా సహాయపడగలను?"
                    elif pref_lang == "hi":
                        reply = "मैं हेल्थएआई ग्लोबल असिस्टेंट हूँ। मैं आपको डॉक्टर ढूंढने, अपॉइंटमेंट बुक करने, मेडिकल रिकॉर्ड देखने या लक्षणों का विश्लेषण करने में मदद कर सकता हूँ। आज मैं आपकी क्या मदद कर सकता हूँ?"
                    else:
                        reply = "I am the HealthAI Global Assistant. I can help you find doctors, book appointments, view your medical records, or analyze symptoms. How can I help you today?"

            # Yield rule-based if needed
            import json
            if reply and not has_groq and not has_hf:
                yield f"data: {json.dumps({'type': 'chunk', 'content': reply})}\n\n"

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
                            user_query = input_data.message.lower()
                            user_query_words = set(user_query.split())
                        
                            has_hi_char = any(ord(c) >= 0x0900 and ord(c) <= 0x097F for c in user_query)
                            has_te_char = any(ord(c) >= 0x0C00 and ord(c) <= 0x0C7F for c in user_query)
                        
                            is_hinglish = any(w in user_query_words for w in hinglish_words)
                            is_tinglish = any(w in user_query_words for w in tinglish_words)
                        
                            if has_te_char:
                                reply = "అపాయింట్‌మెంట్ బుక్ చేయడానికి, నాకు మరికొన్ని వివరాలు కావాలి. మీరు ఏ వైద్యుడిని సంప్రదించాలనుకుంటున్నారు, మరియు ఏ తేదీ మరియు సమయంలో?"
                            elif has_hi_char:
                                reply = "अपॉइंटमेंट बुक करने के लिए, मुझे कुछ और विवरण चाहिए। आप किस डॉक्टर से मिलना चाहते हैं, और किस तारीख और समय पर?"
                            elif is_tinglish:
                                reply = "Appointment book cheyyడానికి naku konchem details kavali. Meeku ey doctor kavali, ey date and time lo consult chestharu?"
                            elif is_hinglish:
                                reply = "Appointment book karne ke liye mujhe thode aur details chahiye. Aap kis doctor se milna chahte hain, aur kis date aur time par?"
                            else:
                                if pref_lang == "te":
                                    reply = "అపాయింట్‌మెంట్ బుక్ చేయడానికి, నాకు మరికొన్ని వివరాలు కావాలి. మీరు ఏ వైద్యుడిని సంప్రదించాలనుకుంటున్నారు, మరియు ఏ తేదీ మరియు సమయంలో?"
                                elif pref_lang == "hi":
                                    reply = "अपॉइंटमेंट बुक करने के लिए, मुझे कुछ और विवरण चाहिए। आप किस डॉक्टर से मिलना चाहते हैं, और किस तारीख और समय पर?"
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

            # Guard action checks based on dynamic Role-Based Access Control (RBAC)
            user_role = current_user.role
            role_permissions = SYSTEM_CAPABILITIES.get("roles", {}).get(user_role, {}).get("permissions", [])
            
            # Check if the user is trying to perform patient-only actions (booking/finding doctors) without permission
            msg_lower = input_data.message.lower()
            is_trying_patient_action = False
            blocked_act_type = ""
            
            if "book_appointment" not in role_permissions and any(k in msg_lower for k in ["book", "schedule", "appointment"]):
                is_trying_patient_action = True
                blocked_act_type = "book_appointment"
            elif "find_doctors" not in role_permissions and any(k in msg_lower for k in ["find", "search", "doctor", "specialist"]):
                is_trying_patient_action = True
                blocked_act_type = "find_doctors"
                
            if is_trying_patient_action:
                action = None
                if user_role == "doctor":
                    reply = f"Access Denied: As a registered doctor, you cannot book or browse appointments or execute '{blocked_act_type}'."
                elif user_role == "admin":
                    reply = f"Access Denied: As an administrator, you cannot book or browse appointments or execute '{blocked_act_type}'."
                else:
                    reply = f"Access Denied: You do not have permission to execute '{blocked_act_type}' under your role."
            elif action:
                act_type = action.get("type")
                # Check if this action is registered in capabilities
                action_info = SYSTEM_CAPABILITIES.get("actions", {}).get(act_type)
                
                if not action_info:
                    action = None
                    reply = "I'm sorry, that action is not supported by the system capabilities."
                elif act_type not in role_permissions:
                    action = None
                    # Generate a polite denial based on role
                    if user_role == "doctor":
                        reply = f"Access Denied: As a registered doctor, you cannot book or browse appointments or execute '{act_type}'."
                    elif user_role == "admin":
                        reply = f"Access Denied: As an administrator, you cannot book or browse appointments or execute '{act_type}'."
                    else:
                        reply = f"Access Denied: You do not have permission to execute '{act_type}' under your role."
            
            # Save assistant reply
            assistant_msg = models.Message(
                conversation_id=conv.id,
                role="assistant",
                content=f"{reply}\n\n[Disclaimer: {disclaimer}]"
            )
            db.add(assistant_msg)
            db.commit()

            import json
            yield f"data: {json.dumps({'type': 'action', 'action': action, 'disclaimer': disclaimer, 'reply': reply})}\n\n" 
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Assistant error: {str(e)}"
            )

    return StreamingResponse(generate(), media_type="text/event-stream")

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
