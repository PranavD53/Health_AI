import os
import datetime
import random
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from app.database import get_db
from app import models
from app.routes.auth import get_current_user
from app.routes.appointments import AppointmentResponse
from app.routes.symptoms import SymptomLogResponse
from app.routes.records import MedicalRecordResponse

router = APIRouter(prefix="/dashboard-data", tags=["Dashboard"])

# --- Pydantic Schemas ---
class MetricResponse(BaseModel):
    heart_rate: str
    sleep: str
    steps: str

class ActivityLogResponse(BaseModel):
    id: int
    action: str
    details: Optional[str] = None
    timestamp: datetime.datetime

class DashboardResponse(BaseModel):
    upcoming_appointments: List[AppointmentResponse]
    recent_symptom_logs: List[SymptomLogResponse]
    medical_records: List[MedicalRecordResponse]
    health_tip: str
    metrics: MetricResponse
    activity_logs: List[ActivityLogResponse]

# --- Static Fallback Health Tips ---
HEALTH_TIPS = [
    "Stay hydrated! Aim to drink at least 8-10 glasses of water daily to support digestion, energy, and overall health.",
    "Prioritize 7-8 hours of restful sleep tonight. Quality sleep is essential for muscle repair, focus, and immune function.",
    "Try incorporating 30 minutes of moderate activity, such as brisk walking, to improve cardiovascular strength and mood.",
    "Fill half your plate with colorful vegetables and fruits to supply your body with vital antioxidants and fiber.",
    "Take 5 minutes today for deep breathing or mindfulness. Managing stress goes a long way toward regulating blood pressure.",
    "Limit processed sugars and focus on whole food sources to stabilize energy levels and prevent mid-day crashes."
]

async def fetch_ai_health_tip() -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
    
    if has_valid_key:
        try:
            async with httpx.AsyncClient() as client:
                system_prompt = (
                    "You are a helpful wellness and healthcare assistant. "
                    "Give a single, concise daily health or wellness tip."
                )
                user_prompt = "Generate a single random, concise health tip in 1-2 sentences. Return only the tip text."
                
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.7,
                        "max_tokens": 100
                    },
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    res_json = response.json()
                    tip = res_json["choices"][0]["message"]["content"].strip()
                    # Strip quotes if the model returned them
                    if tip.startswith('"') and tip.endswith('"'):
                        tip = tip[1:-1]
                    return tip
        except Exception as e:
            print(f"Failed to fetch AI health tip: {e}")
            
    return random.choice(HEALTH_TIPS)

# --- Endpoints ---

@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        # 1. Upcoming appointments (booked, today or future date)
        appointments = db.query(models.Appointment).filter(
            models.Appointment.patient_id == current_user.id,
            models.Appointment.status == "booked",
            models.Appointment.date >= today_str
        ).order_by(models.Appointment.date.asc(), models.Appointment.time.asc()).all()

        # 2. Recent symptom logs (last 5 entries)
        symptoms = db.query(models.SymptomLog).filter(
            models.SymptomLog.user_id == current_user.id
        ).order_by(models.SymptomLog.created_at.desc()).limit(5).all()

        # 3. Medical records (last 5 entries)
        records = db.query(models.MedicalRecord).filter(
            models.MedicalRecord.user_id == current_user.id
        ).order_by(models.MedicalRecord.uploaded_at.desc()).limit(5).all()

        # 4. AI Health Tip
        health_tip = await fetch_ai_health_tip()

        # 5. Patient Metrics
        hr = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "heart_rate").order_by(models.PatientMetric.recorded_at.desc()).first()
        sl = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "sleep").order_by(models.PatientMetric.recorded_at.desc()).first()
        st = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "steps").order_by(models.PatientMetric.recorded_at.desc()).first()
        
        metrics_data = {
            "heart_rate": hr.value if hr else "72 bpm",
            "sleep": sl.value if sl else "7h 45m Deep",
            "steps": st.value if st else "8,432 steps"
        }

        # 6. User Activity Logs
        logs = db.query(models.AuditLog).filter(
            models.AuditLog.user_id == current_user.id
        ).order_by(models.AuditLog.timestamp.desc()).limit(5).all()
        
        activity_logs = []
        for log in logs:
            activity_logs.append({
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "timestamp": log.timestamp
            })
            
        if not activity_logs:
            activity_logs = [
                {
                    "id": 1,
                    "action": "Welcome",
                    "details": "Account initialized.",
                    "timestamp": current_user.created_at
                }
            ]

        return {
            "upcoming_appointments": appointments,
            "recent_symptom_logs": symptoms,
            "medical_records": records,
            "health_tip": health_tip,
            "metrics": metrics_data,
            "activity_logs": activity_logs
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while compiling the dashboard: {str(e)}"
        )
