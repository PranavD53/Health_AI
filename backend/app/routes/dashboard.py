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
from app.routes.doctors import translate_doctor, DOCTOR_TRANSLATIONS

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

HEALTH_TIPS_HI = [
    "हाइड्रेटेड रहें! पाचन, ऊर्जा और समग्र स्वास्थ्य का समर्थन करने के लिए रोजाना कम से कम 8-10 गिलास पानी पीने का लक्ष्य रखें।",
    "आज रात 7-8 घंटे की आरामदायक नींद को प्राथमिकता दें। मांसपेशियों की मरम्मत, ध्यान केंद्रित करने और प्रतिरक्षा कार्य के लिए गुणवत्तापूर्ण नींद आवश्यक है।",
    "कार्डियोवैश्वुलर ताकत और मूड को बेहतर करने के लिए 30 मिनट की मध्यम गतिविधि, जैसे तेज चलना, शामिल करने का प्रयास करें।",
    "अपने शरीर को महत्वपूर्ण एंटीऑक्सीडेंट और फाइबर की आपूर्ति करने के लिए अपनी प्लेट के आधे हिस्से को रंगीन सब्जियों और फलों से भरें।",
    "गहरी सांस लेने या माइंडफुलनेस के लिए आज 5 मिनट का समय निकालें। तनाव का प्रबंधन करना रक्तचाप को नियंत्रित करने में बहुत मदद करता है।",
    "प्रसंस्कृत शर्करा को सीमित करें और ऊर्जा के स्तर को स्थिर करने और दोपहर के समय की मंदी को रोकने के लिए संपूर्ण खाद्य स्रोतों पर ध्यान केंद्रित करें।"
]

HEALTH_TIPS_TE = [
    "హైడ్రేటెడ్ గా ఉండండి! జీర్ణక్రియ, శక్తి మరియు మొత్తం ఆరోగ్యానికి తోడ్పడటానికి రోజుకు కనీసం 8-10 గ్లాసుల నీరు త్రాగాలని లక్ష్యంగా పెట్టుకోండి.",
    "ఈ రాత్రి 7-8 గంటల ప్రశాంతమైన నిద్రకు ప్రాధాన్యత ఇవ్వండి. కండరాల మరమ్మత్తు, ఏకాగ్రత మరియు రోగనిరోధక శక్తి కోసం నాణ్యమైన నిద్ర చాలా అవసరం.",
    "గుండె బలాన్ని మరియు మానసిక స్థితిని మెరుగుపరచడానికి 30 నిమిషాల మధ్యస్థ కార్యాచరణను, ఉదాహరణకు వేగంగా నడవడం వంటివి చేర్చడానికి ప్రయత్నించండి.",
    "మీ శరీరానికి అవసరమైన యాంటీఆక్సిడెంట్లు మరియు ఫైబర్‌లను అందించడానికి మీ ప్లేట్‌లో సగం రంగురంగుల కూరగాయలు మరియు పండ్లతో నింపండి.",
    "ఈ రోజు లోతైన శ్వాస లేదా మైండ్‌ఫుల్‌నెస్ కోసం 5 నిమిషాలు కేటాయించండి. రక్తపోటును నియంత్రించడంలో ఒత్తిడిని నిర్వహించడం చాలా సహాయపడుతుంది.",
    "ప్రాసెస్ చేసిన చక్కెరలను పరిమితం చేయండి మరియు శక్తి స్థాయిలను స్థిరంగా ఉంచడానికి మరియు మధ్యాహ్నం అలసటను నివారించడానికి సహజ ఆహార వనరులపై దృష్టి పెట్టండి."
]

async def fetch_ai_health_tip(lang: str = "en") -> str:
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
    
    if has_valid_key:
        try:
            async with httpx.AsyncClient() as client:
                system_prompt = (
                    "You are a helpful wellness and healthcare assistant. "
                    "Give a single, concise daily health or wellness tip."
                )
                
                lang_name = "English"
                if lang == "hi":
                    lang_name = "Hindi"
                elif lang == "te":
                    lang_name = "Telugu"
                    
                user_prompt = f"Generate a single random, concise health tip in 1-2 sentences. Return only the tip text in the language: {lang_name}."
                
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
                        "max_tokens": 120
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
            
    if lang == "hi":
        return random.choice(HEALTH_TIPS_HI)
    elif lang == "te":
        return random.choice(HEALTH_TIPS_TE)
    return random.choice(HEALTH_TIPS)

# --- Endpoints ---

@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    lang: Optional[str] = "en",
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
        health_tip = await fetch_ai_health_tip(lang)

        # 5. Patient Metrics
        hr = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "heart_rate").order_by(models.PatientMetric.recorded_at.desc()).first()
        sl = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "sleep").order_by(models.PatientMetric.recorded_at.desc()).first()
        st = db.query(models.PatientMetric).filter(models.PatientMetric.user_id == current_user.id, models.PatientMetric.metric_type == "steps").order_by(models.PatientMetric.recorded_at.desc()).first()
        
        metrics_data = {
            "heart_rate": hr.value if hr else "72 bpm",
            "sleep": sl.value if sl else "7h 45m Deep",
            "steps": st.value if st else "8,432 steps"
        }

        # 6. User Activity Logs (Previously Booked Appointments only)
        appts = db.query(models.Appointment).filter(
            models.Appointment.patient_id == current_user.id,
            models.Appointment.status != "cancelled"
        ).order_by(models.Appointment.created_at.desc()).limit(5).all()

        # Translate language
        lang_code = "en"
        if lang:
            preferred = lang.split(",")[0].strip().lower()
            if preferred.startswith("hi"):
                lang_code = "hi"
            elif preferred.startswith("te"):
                lang_code = "te"

        appointments_resp = []
        for appt in appointments:
            appt_resp = AppointmentResponse.from_orm(appt)
            if appt_resp.doctor:
                translate_doctor(appt_resp.doctor, lang_code)
            appointments_resp.append(appt_resp)
        
        activity_logs = []
        for app in appts:
            doc = db.query(models.Doctor).filter(models.Doctor.id == app.doctor_id).first()
            doc_name = doc.name if doc else "Doctor"
            if doc_name != "Doctor" and lang_code in ["hi", "te"] and doc_name in DOCTOR_TRANSLATIONS[lang_code]:
                doc_name = DOCTOR_TRANSLATIONS[lang_code][doc_name]["name"]
            activity_logs.append({
                "id": app.id,
                "action": "Appointment Booked",
                "details": f"Scheduled with {doc_name} on {app.date} at {app.time}",
                "timestamp": app.created_at
            })
            
        if not activity_logs:
            activity_logs = [
                {
                    "id": 1,
                    "action": "Welcome",
                    "details": "Account initialized. No appointments booked yet.",
                    "timestamp": current_user.created_at
                }
            ]

        return {
            "upcoming_appointments": appointments_resp,
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
