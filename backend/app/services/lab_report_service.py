import os
import json
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.ocr.extractor import extract_text
from app.rules.lab_test_classifier import classify_test_type, parse_lab_values
from app.services.llm_client import call_llm
from app import models

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "prompts", "lab_summary_prompt.txt")

def load_prompt() -> str:
    try:
        with open(PROMPT_PATH, "r") as f:
            return f.read()
    except Exception:
        return "Summarize these lab results in plain language, explaining HIGH/LOW flags. Do NOT diagnose."

async def process_upload(db: Session, patient_id: int, file_bytes: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    # 1. OCR Extraction
    ext_result = extract_text(file_bytes, content_type)
    text = ext_result.get("text", "")
    confidence = ext_result.get("confidence", 0.0)
    
    # Check extraction quality
    if not text or confidence < 0.6:
        log = models.LabReportLog(
            file_reference=filename,
            extraction_status="FAILED" if not text else "LOW_CONFIDENCE"
        )
        db.add(log)
        db.commit()
        return {
            "success": False,
            "response": "Unable to read this report clearly, please re-upload a clearer copy."
        }
        
    # 2. Rule Engine: Classify Test Type
    test_type = classify_test_type(text)
    
    if not test_type:
        log = models.LabReportLog(
            file_reference=filename,
            extraction_status="SUCCESS",
            detected_test_type="UNSUPPORTED"
        )
        db.add(log)
        db.commit()
        return {
            "success": False,
            "response": "This report type isn't currently supported by automatic analysis. Please share this report with your doctor directly."
        }
        
    # 3. Rule Engine: Parse Values
    parsed_values, flags = parse_lab_values(text, test_type)
    
    # 4. LLM Summary
    system_prompt = load_prompt()
    user_prompt = f"Test Type: {test_type}\nExtracted Values: {json.dumps(parsed_values)}\nFlags: {json.dumps(flags)}"
    
    # Note: we ask LLM for plain text, not JSON, based on user requirements for Lab report summarization
    llm_result = await call_llm(system_prompt, user_prompt, require_json=False)
    conclusion = llm_result.get("content", "Analysis complete.")
    
    # 5. Determine case status
    status = "PENDING_REVIEW" if flags else "RESOLVED"
    
    case = models.LabReportCase(
        patient_id=patient_id,
        test_type=test_type,
        status=status
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    
    log = models.LabReportLog(
        case_id=case.id,
        file_reference=filename,
        extraction_status="SUCCESS",
        detected_test_type=test_type,
        parsed_values=parsed_values,
        flags=flags,
        llm_conclusion=conclusion
    )
    db.add(log)
    db.commit()
    
    response_msg = f"Lab Report Analysis for {test_type}:\n\n{conclusion}"
    if flags:
        response_msg += "\n\nI have flagged some abnormal values and created a case for your doctor to review."
        
    return {
        "success": True,
        "response": response_msg,
        "case_id": case.id,
        "test_type": test_type,
        "flags": flags
    }
