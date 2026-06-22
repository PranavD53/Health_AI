import os
from app.timezone_helper import datetime
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
from fastapi.encoders import ENCODERS_BY_TYPE

# Globally encode naive datetimes with Z to avoid browser-local parsing shift
ENCODERS_BY_TYPE[datetime.datetime] = lambda dt: dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()

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
    if os.getenv("TESTING") in ("True", "true"):
        print("Skipping production startup DB setup during testing.")
        return
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
from app.routes import voice_socket
app.include_router(voice_socket.router)
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


from fastapi import UploadFile, File

@app.post("/tars/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    groq_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    import httpx
    # Use key from header or environment
    key = groq_key or os.getenv("GROQ_API_KEY", "")
    if not key or key.startswith("your_groq_api_key"):
        raise HTTPException(status_code=400, detail="Groq API key not configured")
        
    try:
        content_bytes = await file.read()
        filename = file.filename or "voice.webm"
        
        # Call Groq Whisper API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {key}"
                },
                files={
                    "file": (filename, content_bytes, file.content_type or "audio/webm")
                },
                data={
                    "model": "whisper-large-v3"
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                res_json = response.json()
                return {"text": res_json.get("text", "")}
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Whisper API error: {response.text}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error transcribing audio: {str(e)}")


@app.get("/uploads/{filename}")
def serve_db_upload(filename: str, db: Session = Depends(get_db)):
    # Query database for MedicalRecord
    record = db.query(models.MedicalRecord).filter(
        (models.MedicalRecord.file_name == filename) |
        models.MedicalRecord.file_path.like(f"%/uploads/{filename}")
    ).first()
    
    import base64
    from fastapi.responses import Response
    
    if record and record.file_data:
        try:
            content_bytes = base64.b64decode(record.file_data)
            return Response(content=content_bytes, media_type=record.file_type or "application/octet-stream")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decode file: {str(e)}")
            
    # If not found in MedicalRecord, check if it's a Doctor profile picture or license document
    doctor = db.query(models.Doctor).filter(
        (models.Doctor.profile_picture.like(f"%/uploads/{filename}")) |
        (models.Doctor.license_document_path.like(f"%/uploads/{filename}"))
    ).first()
    
    if doctor:
        try:
            # Check if it matches the profile picture
            if doctor.profile_picture and filename in doctor.profile_picture:
                data = doctor.profile_picture_data
                mime = "image/png" if filename.lower().endswith(".png") else ("image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "application/octet-stream")
            else:
                data = doctor.license_document_data
                mime = "application/pdf" if filename.lower().endswith(".pdf") else "application/octet-stream"
            
            if data:
                content_bytes = base64.b64decode(data)
                return Response(content=content_bytes, media_type=mime)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decode doctor file: {str(e)}")
            
    # Fall back to checking if the file is on disk in UPLOADS_DIR
    local_path = os.path.join(UPLOADS_DIR, filename)
    if os.path.exists(local_path):
        from fastapi.responses import FileResponse
        return FileResponse(local_path)
        
    raise HTTPException(status_code=404, detail="File not found")


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
            data_str = await websocket.receive_text()
            try:
                import json
                data = json.loads(data_str)
                if data.get("event") == "signal":
                    to_user_id = data.get("to_user_id")
                    signal_data = data.get("data")
                    if to_user_id:
                        await manager.send_personal_json({
                            "event": "signal",
                            "from_user_id": user.id,
                            "data": signal_data
                        }, int(to_user_id))
            except Exception:
                pass
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

class DoctorLeaveRequestInfo(BaseModel):
    id: int
    start_date: str
    end_date: str
    reason: Optional[str] = None
    status: str

class DoctorDashboardResponse(BaseModel):
    id: int
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
    leave_requests: Optional[List[DoctorLeaveRequestInfo]] = []

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

        # Query doctor leaves
        leaves = db.query(models.LeaveRequest).filter(models.LeaveRequest.doctor_id == doctor.id).order_by(models.LeaveRequest.created_at.desc()).all()
        leave_logs = []
        for lr in leaves:
            leave_logs.append({
                "id": lr.id,
                "start_date": lr.start_date,
                "end_date": lr.end_date,
                "reason": lr.reason,
                "status": lr.status
            })

        return {
            "id": doctor.id,
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
            "pending_appointments": pending_appointments,
            "leave_requests": leave_logs
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
    gemini_key: Optional[str] = None
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
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key = input_data.groq_key or os.getenv("GROQ_API_KEY", "")
    hf_key = input_data.hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))
    
    has_gemini = gemini_key and not gemini_key.startswith("your_gemini_api_key")
    has_groq = groq_key and not groq_key.startswith("your_groq_api_key")
    has_hf = hf_key and not hf_key.startswith("your_hf_api_key")
    
    system_instruction_text = (
        "You are a confirmation parser. Determine if the user's message represents an agreement/confirmation, a disagreement/cancellation, or if it is ambiguous.\n"
        "Classify the intent into one of:\n"
        "- 'affirmative' (agreement, yes, proceed, correct, confirm, haan, avunu, etc.)\n"
        "- 'negative' (disagreement, no, cancel, stop, vaddu, nahi, etc.)\n"
        "- 'ambiguous' (anything else)\n\n"
        "Output ONLY a raw JSON block with 'intent' key. Example:\n"
        "{\"intent\": \"affirmative\"}"
    )

    messages_payload = [
        {
            "role": "system",
            "content": system_instruction_text
        },
        {"role": "user", "content": f"User message: \"{input_data.message}\""}
    ]
    
    if has_gemini:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"role": "user", "parts": [{"text": f"User message: \"{input_data.message}\""}]}],
                        "systemInstruction": {
                            "parts": [{"text": system_instruction_text}]
                        },
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": {
                                "type": "OBJECT",
                                "properties": {
                                    "intent": {"type": "STRING"}
                                },
                                "required": ["intent"]
                            }
                        }
                    },
                    timeout=5.0
                )
                if response.status_code == 200:
                    res_json = response.json()
                    parts = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                    if parts:
                        content_res = parts[0].get("text", "").strip()
                        import re
                        match = re.search(r'\{.*?\}', content_res)
                        if match:
                            parsed = json.loads(match.group(0))
                            if parsed.get("intent") in ["affirmative", "negative", "ambiguous"]:
                                return {"intent": parsed["intent"]}
        except Exception:
            pass

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
    # Determine language preference and detect language style dynamically
    pref_lang = "en"
    if input_data.language:
        pref_lang = input_data.language.split("-")[0].strip().lower()
    elif accept_language:
        pref_lang = accept_language.split(",")[0].split("-")[0].strip().lower()

    async def generate():
        import json
        import asyncio
        from app.services.tars_engine import execute_tars_intent

        try:
            result = await execute_tars_intent(
                message=input_data.message,
                current_user=current_user,
                db=db,
                gemini_key=input_data.gemini_key or "",
                groq_key=input_data.groq_key or "",
                hf_key=input_data.hf_key or "",
                language=pref_lang
            )

            message = result["message"]
            disclaimer = result["disclaimer"]
            action_payload = result["action"]

            # Stream message chunk-by-chunk to preserve typing effect
            chunk_size = 4
            for i in range(0, len(message), chunk_size):
                chunk = message[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)

            # Yield action payload and final message mapping to complete the call
            yield f"data: {json.dumps({'type': 'action', 'action': action_payload, 'disclaimer': disclaimer, 'reply': message})}\n\n"
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
    latitude: Optional[float] = None
    longitude: Optional[float] = None
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
async def trigger_sos(
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
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
            latitude=latitude,
            longitude=longitude,
            status="active"
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        
        alert_details = ""
        # Alert doctors within 100km radius if patient coords are present
        if latitude is not None and longitude is not None:
            import math
            def get_distance_km(lat1, lon1, lat2, lon2):
                R = 6371.0
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
                return R * c

            # Query all registered doctors with coordinates
            doctors = db.query(models.Doctor).filter(
                models.Doctor.latitude != None,
                models.Doctor.longitude != None
            ).all()

            notified_docs = []
            from app.websocket_manager import manager

            for doc in doctors:
                dist = get_distance_km(latitude, longitude, doc.latitude, doc.longitude)
                if dist <= 100.0:
                    notified_docs.append(f"{doc.name} ({dist:.1f} km away)")
                    # Save DB Notification for doctor user
                    if doc.user_id:
                        notif = models.Notification(
                            user_id=doc.user_id,
                            message=f"CRITICAL SOS EMERGENCY: Patient {patient_name} has triggered an alert at ({latitude}, {longitude}) within {dist:.1f} km of your clinic.",
                            notification_type="general",
                            related_id=alert.id
                        )
                        db.add(notif)
                        # Send real-time socket alert
                        await manager.send_personal_json({
                            "event": "new_alert",
                            "message": f"CRITICAL SOS: {patient_name} triggered emergency SOS within {dist:.1f} km of you!"
                        }, doc.user_id)

            if notified_docs:
                alert_details = f" Alerted doctors within 100km radius: " + ", ".join(notified_docs)
                # Broadcast alert event to trigger verification on admin/doctor dashboard WS
                await manager.broadcast_json({"event": "new_alert"})
            else:
                alert_details = " No doctors found within 100km radius."
            
            db.commit()

        log_action(db, current_user.id, "EMERGENCY_SOS_TRIGGERED", f"SOS triggered by {patient_name}. Address: {patient_address}.{alert_details}")
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

# --- Medicine Reminders ---
class MedicineReminderCreate(BaseModel):
    medicine_name: str
    dosage: str
    time: str
    days: Optional[str] = "Daily"
    method: str # app, email, sms
    contact_info: Optional[str] = None

class MedicineReminderResponse(BaseModel):
    id: int
    medicine_name: str
    dosage: str
    time: str
    days: Optional[str]
    method: str
    contact_info: Optional[str]
    is_active: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@app.get("/reminders", response_model=List[MedicineReminderResponse])
def get_reminders(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        reminders = db.query(models.MedicineReminder).filter(models.MedicineReminder.user_id == current_user.id).all()
        return reminders
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reminders", response_model=MedicineReminderResponse)
def create_reminder(
    data: MedicineReminderCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Default contact info to email if none provided and method is email
        contact = data.contact_info
        if not contact:
            contact = current_user.email

        reminder = models.MedicineReminder(
            user_id=current_user.id,
            medicine_name=data.medicine_name,
            dosage=data.dosage,
            time=data.time,
            days=data.days,
            method=data.method,
            contact_info=contact,
            is_active=True
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)

        # Trigger Brevo initial confirmation if method is email
        if data.method == "email":
            try:
                from app.routes.auth import send_via_brevo
                html_body = f"""
                <h3>Medicine Reminder Scheduled</h3>
                <p>Hello,</p>
                <p>You have scheduled a medicine reminder for <strong>{data.medicine_name}</strong> ({data.dosage}) to be taken daily at <strong>{data.time}</strong>.</p>
                <p>We will alert you at the scheduled time.</p>
                <p>Best regards,<br>HealthAI Assistant</p>
                """
                send_via_brevo(contact, "Medicine Reminder Scheduled - HealthAI", html_body)
                print(f"[Brevo] Scheduled reminder email sent to {contact}")
            except Exception as email_err:
                print(f"[Brevo] Failed to send scheduled reminder email: {email_err}")

        elif data.method == "sms":
            # Log simulated SMS send
            print(f"[SMS ALERT] Simulated SMS sent to {contact}: Reminder set for {data.medicine_name} at {data.time}")

        log_action(db, current_user.id, "CREATE_REMINDER", f"Reminder set for {data.medicine_name} at {data.time} via {data.method}")
        return reminder
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/reminders/{id}")
def delete_reminder(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        reminder = db.query(models.MedicineReminder).filter(
            models.MedicineReminder.id == id,
            models.MedicineReminder.user_id == current_user.id
        ).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        db.delete(reminder)
        db.commit()
        log_action(db, current_user.id, "DELETE_REMINDER", f"Deleted reminder ID {id}")
        return {"status": "success", "message": "Reminder deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/reminders/{id}/toggle")
def toggle_reminder(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        reminder = db.query(models.MedicineReminder).filter(
            models.MedicineReminder.id == id,
            models.MedicineReminder.user_id == current_user.id
        ).first()
        if not reminder:
            raise HTTPException(status_code=404, detail="Reminder not found")
        reminder.is_active = not reminder.is_active
        db.commit()
        db.refresh(reminder)
        log_action(db, current_user.id, "TOGGLE_REMINDER", f"Toggled reminder ID {id} to {reminder.is_active}")
        return {"status": "success", "message": f"Reminder status updated to {reminder.is_active}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class AppointmentPriorityUpdate(BaseModel):
    priority: str

@app.post("/appointment/{id}/priority")
def update_appointment_priority(
    id: int,
    data: AppointmentPriorityUpdate,
    current_user: models.User = Depends(require_role(["doctor", "admin"])),
    db: Session = Depends(get_db)
):
    try:
        appt = db.query(models.Appointment).filter(models.Appointment.id == id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        
        if current_user.role == "doctor":
            doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
            if not doctor or appt.doctor_id != doctor.id:
                raise HTTPException(status_code=403, detail="Unauthorized to modify this appointment priority")
                
        appt.priority = data.priority
        db.commit()
        log_action(db, current_user.id, "UPDATE_APPOINTMENT_PRIORITY", f"Set appointment ID {id} priority to {data.priority}")
        return {"status": "success", "message": f"Appointment priority updated to {data.priority}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
