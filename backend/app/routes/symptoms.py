import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import httpx

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action

router = APIRouter(prefix="/symptom", tags=["Symptom Assessment"])

# --- Pydantic Schemas ---
class SymptomAnalyze(BaseModel):
    symptoms: str
    severity: str # mild, moderate, severe
    duration: str # e.g., "3 days"

class SymptomLogResponse(BaseModel):
    id: int
    user_id: int
    symptoms: str
    severity: str
    duration: str
    risk_category: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class SymptomAnalysisResponse(BaseModel):
    symptom_log: SymptomLogResponse
    emergency_alert: bool
    alert_message: Optional[str] = None
    ai_recommendation: Optional[str] = None
    disclaimer: str

# --- Emergency Detection Config ---
EMERGENCY_KEYWORDS = [
    "chest pain", "can't breathe", "stroke", 
    "unconscious", "loss of consciousness", "bleeding", "heavy bleeding", "suicide", "heart attack", 
    "difficulty breathing", "extreme difficulty breathing", "slurred speech", "facial drooping",
    "seizure", "seizures", "acute seizures", "anaphylactic", "anaphylaxis", "allergic reaction",
    # Hindi emergency keywords
    "छाती में दर्द", "सांस लेने में तकलीफ", "लकवा", "स्ट्रोक", "खून बहना", "दिल का दौरा", "आत्महत्या",
    # Telugu emergency keywords
    "గుండె నొప్పి", "గుండెల్లో నొప్పి", "శ్వాస తీసుకోవడంలో ఇబ్బంది", "పక్షవాతం", "రక్తం కారడం", "రక్తస్రావం", "గుండెపోటు", "ఆత్మహత్య"
]

def scan_for_emergency(text: str) -> bool:
    cleaned_text = text.lower()
    return any(keyword in cleaned_text for keyword in EMERGENCY_KEYWORDS)

# --- Endpoints ---

@router.post("/analyze", response_model=SymptomAnalysisResponse)
async def analyze_symptoms(
    data: SymptomAnalyze,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # 1. Check for emergency keywords
        is_emergency = scan_for_emergency(data.symptoms) or data.severity.lower() == "severe" and "chest" in data.symptoms.lower()
        
        risk_category = "Routine"
        ai_recommendation = None
        alert_message = None

        if is_emergency:
            risk_category = "Emergency"
            alert_message = "EMERGENCY: Emergency symptoms detected. Please call 108 or your local emergency services immediately."
            ai_recommendation = "Seek immediate emergency medical care. Do not wait for an appointment."
            
            # Log emergency event
            log_action(
                db, 
                current_user.id, 
                "EMERGENCY_DETECTED", 
                f"Emergency keywords detected in symptoms: '{data.symptoms}'. Severity: {data.severity}."
            )
        else:
            # 2. Query Groq API for non-emergency analysis
            groq_key = os.getenv("GROQ_API_KEY", "")
            has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
            
            if has_valid_key:
                try:
                    async with httpx.AsyncClient() as client:
                        # Construct system and user prompts
                        system_prompt = (
                            "You are a helpful medical assistant. Give general health information only. "
                            "Always recommend consulting a doctor. Never diagnose or prescribe medication."
                        )
                        user_prompt = (
                            f"Analyze the following symptoms:\n"
                            f"Symptoms: {data.symptoms}\n"
                            f"Severity: {data.severity}\n"
                            f"Duration: {data.duration}\n\n"
                            f"Return a JSON object containing:\n"
                            f"1. 'risk_category': select strictly one of [Urgent, Routine, Self-Care].\n"
                            f"2. 'recommendation': a brief health recommendation (max 2 sentences).\n"
                            f"Response format must be valid JSON only: {{\"risk_category\": \"...\", \"recommendation\": \"...\"}}"
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
                                    {"role": "system", "content": system_prompt},
                                    {"role": "user", "content": user_prompt}
                                ],
                                "response_format": {"type": "json_object"},
                                "temperature": 0.2
                            },
                            timeout=8.0
                        )
                        
                        if response.status_code == 200:
                            res_json = response.json()
                            content = res_json["choices"][0]["message"]["content"]
                            import json
                            parsed_data = json.loads(content)
                            
                            risk_category = parsed_data.get("risk_category", "Routine")
                            ai_recommendation = parsed_data.get("recommendation", "Please consult a doctor.")
                            
                            # Standardize risk categories
                            valid_risks = ["Emergency", "Urgent", "Routine", "Self-Care"]
                            if risk_category not in valid_risks:
                                risk_category = "Routine"
                        else:
                            raise Exception(f"Groq API returned status code {response.status_code}")
                except Exception as e:
                    # Fallback to rule-based analysis if Groq fails
                    print(f"Groq API call failed, falling back to rules: {e}")
                    if data.severity.lower() == "severe":
                        risk_category = "Urgent"
                        ai_recommendation = "Your symptoms are severe. We recommend visiting an urgent care clinic or consulting a doctor soon."
                    elif data.severity.lower() == "moderate":
                        risk_category = "Routine"
                        ai_recommendation = "Your symptoms are moderate. We recommend scheduling a routine visit with a primary care doctor."
                    else:
                        risk_category = "Self-Care"
                        ai_recommendation = "Your symptoms appear mild. Rest, stay hydrated, and monitor your condition. Consult a doctor if they persist."
            else:
                # Rule-based fallback if no Groq key is present
                if data.severity.lower() == "severe":
                    risk_category = "Urgent"
                    ai_recommendation = "Symptoms are marked as severe. You should seek medical attention from a doctor promptly."
                elif data.severity.lower() == "moderate":
                    risk_category = "Routine"
                    ai_recommendation = "Symptoms are moderate. Monitor them and book a routine doctor consultation."
                else:
                    risk_category = "Self-Care"
                    ai_recommendation = "Mild symptoms reported. Engage in self-care, rest, and check in if symptoms get worse."

        # 3. Save to database
        db_log = models.SymptomLog(
            user_id=current_user.id,
            symptoms=data.symptoms,
            severity=data.severity,
            duration=data.duration,
            risk_category=risk_category
        )
        db.add(db_log)
        db.commit()
        db.refresh(db_log)

        # Audit logging of the symptom scan
        log_action(db, current_user.id, "SYMPTOM_ANALYZE", f"Analyzed symptoms. Risk: {risk_category}")

        return {
            "symptom_log": db_log,
            "emergency_alert": is_emergency,
            "alert_message": alert_message,
            "ai_recommendation": ai_recommendation,
            "disclaimer": "This is AI-generated information. Please consult a real doctor."
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during symptom analysis: {str(e)}"
        )

@router.get("/history", response_model=List[SymptomLogResponse])
def get_symptom_history(
    patient_user_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # RBAC Check: Patients can only retrieve their own history; Doctor, Admin, Caregiver can view others
        if patient_user_id is not None and patient_user_id != current_user.id:
            if current_user.role not in ["doctor", "admin", "caregiver"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden. You do not have permission to view other patients' symptom histories."
                )
            target_user_id = patient_user_id
        else:
            target_user_id = current_user.id

        history = db.query(models.SymptomLog).filter(
            models.SymptomLog.user_id == target_user_id
        ).order_by(models.SymptomLog.created_at.desc()).all()
        
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving symptom history: {str(e)}"
        )
