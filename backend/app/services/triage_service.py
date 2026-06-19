import os
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.rules.emergency_flags import detect_emergency
from app.rules.triage_whitelist import is_self_care_eligible
from app.services.llm_client import call_llm
from app import models

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "prompts", "symptom_triage_prompt.txt")

def load_prompt() -> str:
    try:
        with open(PROMPT_PATH, "r") as f:
            return f.read()
    except Exception:
        return "You are a medical triage assistant. Respond ONLY with JSON: {'severity': '...', 'symptom_category': '...', 'reasoning': '...', 'patient_facing_message': '...'}"

async def handle_message(db: Session, patient_id: int, message: str) -> Dict[str, Any]:
    # 1. Check emergency flags
    is_emergency, matched_terms = detect_emergency(message)
    
    if is_emergency:
        # Create Case & Log
        case = models.TriageCase(
            patient_id=patient_id,
            ai_severity="EMERGENCY",
            status="EMERGENCY_ALERT",
            symptom_category="EMERGENCY"
        )
        db.add(case)
        db.commit()
        db.refresh(case)
        
        log = models.TriageLog(
            case_id=case.id,
            patient_message=message,
            severity_assigned="EMERGENCY",
            emergency_triggered=True,
            matched_keywords=matched_terms
        )
        db.add(log)
        db.commit()
        
        return {
            "is_emergency": True,
            "response": "EMERGENCY: Severe symptoms detected. Please call your local emergency services (108) or go to the nearest emergency room immediately.",
            "case_id": case.id
        }

    # 2. Not an emergency, call LLM
    system_prompt = load_prompt()
    llm_result = await call_llm(system_prompt, f"Patient reports: {message}", require_json=True)
    
    severity = llm_result.get("severity", "MODERATE")
    symptom_category = llm_result.get("symptom_category", "OTHER")
    patient_message = llm_result.get("patient_facing_message", "I have logged your symptoms.")
    reasoning = llm_result.get("reasoning", "")
    
    # 3. Apply Rule Engine for Self Care
    final_response = ""
    status = "PENDING_REVIEW"
    
    if severity == "MILD":
        eligible, precautions = is_self_care_eligible(symptom_category)
        if eligible:
            final_response = f"{precautions}\n\n{patient_message}"
            status = "RESOLVED"
        else:
            final_response = f"Your symptoms require review. I have created a case for a doctor.\n\n{patient_message}"
    else:
        final_response = f"I've created a case for a doctor to review. This is marked as {severity} priority.\n\n{patient_message}"

    # 4. Save to DB
    case = models.TriageCase(
        patient_id=patient_id,
        ai_severity=severity,
        status=status,
        symptom_category=symptom_category,
        doctor_notes=reasoning
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    
    log = models.TriageLog(
        case_id=case.id,
        patient_message=message,
        ai_raw_response=str(llm_result),
        severity_assigned=severity,
        emergency_triggered=False,
        matched_keywords=[]
    )
    db.add(log)
    db.commit()
    
    return {
        "is_emergency": False,
        "response": final_response,
        "case_id": case.id
    }
