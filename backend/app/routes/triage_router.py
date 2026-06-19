from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user
from app.services.triage_service import handle_message

router = APIRouter(prefix="/chat/symptom", tags=["Symptom Triage"])

class TriageRequest(BaseModel):
    message: str

@router.post("")
async def submit_symptom(
    req: TriageRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Pass to service layer
        result = await handle_message(db, current_user.id, req.message)
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during triage: {str(e)}"
        )

class TriageOverrideRequest(BaseModel):
    doctor_final_severity: str
    doctor_notes: str

@router.patch("/doctor/{case_id}")
def doctor_override(
    case_id: int,
    req: TriageOverrideRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    case = db.query(models.TriageCase).filter(models.TriageCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    case.doctor_final_severity = req.doctor_final_severity
    case.doctor_notes = req.doctor_notes
    db.commit()
    return {"status": "success"}
