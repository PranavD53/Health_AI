import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, require_role, log_action

router = APIRouter(prefix="/feedback", tags=["Feedback"])

# --- Pydantic Schemas ---
class FeedbackSubmit(BaseModel):
    appointment_id: int
    rating_overall: int = Field(..., ge=1, le=5)
    rating_doctor: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None
    rating_communication: Optional[int] = Field(None, ge=1, le=5)
    rating_professionalism: Optional[int] = Field(None, ge=1, le=5)
    rating_wait_time: Optional[int] = Field(None, ge=1, le=5)
    rating_satisfaction: Optional[int] = Field(None, ge=1, le=5)

class FeedbackResponse(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    rating_overall: int
    rating_doctor: int
    comments: Optional[str] = None
    rating_communication: Optional[int] = None
    rating_professionalism: Optional[int] = None
    rating_wait_time: Optional[int] = None
    rating_satisfaction: Optional[int] = None
    is_approved: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

class FeedbackPendingResponse(BaseModel):
    id: int
    doctor_id: int
    doctor_name: str
    specialization: str
    date: str
    time: str

class FeedbackAnalytics(BaseModel):
    average_overall: float
    average_doctor: float
    average_communication: Optional[float] = None
    average_professionalism: Optional[float] = None
    average_wait_time: Optional[float] = None
    average_satisfaction: Optional[float] = None
    total_reviews: int
    rating_distribution: dict # {5: count, 4: count, ...}

# --- Endpoints ---

@router.post("/submit", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    data: FeedbackSubmit,
    edit: bool = Query(False),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check appointment
        appointment = db.query(models.Appointment).filter(models.Appointment.id == data.appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )

        # Validate that the patient owns the appointment
        if appointment.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to submit feedback for this appointment"
            )

        # Validate appointment status is completed
        if appointment.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted after the appointment is completed"
            )

        # Check existing feedback
        existing = db.query(models.Feedback).filter(models.Feedback.appointment_id == data.appointment_id).first()
        
        if existing and not edit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback has already been submitted for this appointment. Set edit=true to modify it."
            )

        if existing:
            # Update fields
            existing.rating_overall = data.rating_overall
            existing.rating_doctor = data.rating_doctor
            existing.comments = data.comments
            existing.rating_communication = data.rating_communication
            existing.rating_professionalism = data.rating_professionalism
            existing.rating_wait_time = data.rating_wait_time
            existing.rating_satisfaction = data.rating_satisfaction
            existing.updated_at = datetime.datetime.utcnow()
            
            db.commit()
            db.refresh(existing)
            log_action(db, current_user.id, "EDIT_FEEDBACK", f"Updated feedback ID {existing.id} for appointment ID {appointment.id}")
            return existing
        else:
            # Create new feedback
            new_feedback = models.Feedback(
                appointment_id=data.appointment_id,
                patient_id=current_user.id,
                doctor_id=appointment.doctor_id,
                rating_overall=data.rating_overall,
                rating_doctor=data.rating_doctor,
                comments=data.comments,
                rating_communication=data.rating_communication,
                rating_professionalism=data.rating_professionalism,
                rating_wait_time=data.rating_wait_time,
                rating_satisfaction=data.rating_satisfaction,
                is_approved=True # Default to approved, admin can moderate
            )
            db.add(new_feedback)
            db.commit()
            db.refresh(new_feedback)
            log_action(db, current_user.id, "SUBMIT_FEEDBACK", f"Submitted feedback ID {new_feedback.id} for appointment ID {appointment.id}")
            return new_feedback

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while submitting feedback: {str(e)}"
        )

@router.get("/appointment/{appointment_id}", response_model=Optional[FeedbackResponse])
def get_feedback_for_appointment(
    appointment_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        feedback = db.query(models.Feedback).filter(models.Feedback.appointment_id == appointment_id).first()
        if not feedback:
            return None
        
        # Verify access: Patient must own it, or Doctor assigned must own it, or Admin
        if current_user.role == "patient" and feedback.patient_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
            
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/pending", response_model=List[FeedbackPendingResponse])
def get_pending_feedbacks(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if current_user.role != "patient":
            return []
            
        # Get completed appointments
        completed_appts = db.query(models.Appointment).filter(
            models.Appointment.patient_id == current_user.id,
            models.Appointment.status == "completed"
        ).all()
        
        res = []
        for appt in completed_appts:
            # Check if feedback already exists
            feedback_exists = db.query(models.Feedback).filter(models.Feedback.appointment_id == appt.id).first()
            if not feedback_exists:
                doctor = db.query(models.Doctor).filter(models.Doctor.id == appt.doctor_id).first()
                res.append({
                    "id": appt.id,
                    "doctor_id": appt.doctor_id,
                    "doctor_name": doctor.name if doctor else "Doctor",
                    "specialization": doctor.specialization if doctor else "General",
                    "date": appt.date,
                    "time": appt.time
                })
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/doctor/{doctor_id}", response_model=List[FeedbackResponse])
def get_doctor_feedbacks(
    doctor_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check if the current user is the doctor themselves or an admin
        is_owner = False
        doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
        if doctor and (doctor.user_id == current_user.id or doctor.contact == current_user.email):
            is_owner = True
            
        is_admin = current_user.role in ["admin", "caregiver"]
        
        query = db.query(models.Feedback).filter(models.Feedback.doctor_id == doctor_id)
        
        # Non-owners/non-admins can only see approved feedbacks
        if not (is_owner or is_admin):
            query = query.filter(models.Feedback.is_approved == True)
            
        feedbacks = query.order_by(models.Feedback.created_at.desc()).all()
        return feedbacks
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/doctor/{doctor_id}/analytics", response_model=FeedbackAnalytics)
def get_doctor_analytics(
    doctor_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Doctor analytics can only be viewed by the doctor themselves or admins
        doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
            
        is_owner = doctor.user_id == current_user.id or doctor.contact == current_user.email
        is_admin = current_user.role in ["admin", "caregiver"]
        
        if not (is_owner or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the doctor or an administrator can view analytics."
            )
            
        feedbacks = db.query(models.Feedback).filter(
            models.Feedback.doctor_id == doctor_id,
            models.Feedback.is_approved == True
        ).all()
        
        total = len(feedbacks)
        if total == 0:
            return {
                "average_overall": 0.0,
                "average_doctor": 0.0,
                "average_communication": 0.0,
                "average_professionalism": 0.0,
                "average_wait_time": 0.0,
                "average_satisfaction": 0.0,
                "total_reviews": 0,
                "rating_distribution": {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
            }
            
        sum_overall = sum(f.rating_overall for f in feedbacks)
        sum_doctor = sum(f.rating_doctor for f in feedbacks)
        
        # Category metrics
        comm_vals = [f.rating_communication for f in feedbacks if f.rating_communication is not None]
        prof_vals = [f.rating_professionalism for f in feedbacks if f.rating_professionalism is not None]
        wait_vals = [f.rating_wait_time for f in feedbacks if f.rating_wait_time is not None]
        sat_vals = [f.rating_satisfaction for f in feedbacks if f.rating_satisfaction is not None]
        
        dist = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for f in feedbacks:
            r = f.rating_doctor
            if r in dist:
                dist[r] += 1
                
        return {
            "average_overall": round(sum_overall / total, 2),
            "average_doctor": round(sum_doctor / total, 2),
            "average_communication": round(sum(comm_vals) / len(comm_vals), 2) if comm_vals else 0.0,
            "average_professionalism": round(sum(prof_vals) / len(prof_vals), 2) if prof_vals else 0.0,
            "average_wait_time": round(sum(wait_vals) / len(wait_vals), 2) if wait_vals else 0.0,
            "average_satisfaction": round(sum(sat_vals) / len(sat_vals), 2) if sat_vals else 0.0,
            "total_reviews": total,
            "rating_distribution": dist
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.get("/admin/all", response_model=List[FeedbackResponse])
def get_admin_feedbacks(
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        return db.query(models.Feedback).order_by(models.Feedback.created_at.desc()).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )

@router.post("/admin/moderate/{id}", response_model=FeedbackResponse)
def moderate_feedback(
    id: int,
    is_approved: bool = Query(...),
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        feedback = db.query(models.Feedback).filter(models.Feedback.id == id).first()
        if not feedback:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
            
        feedback.is_approved = is_approved
        db.commit()
        db.refresh(feedback)
        
        log_action(db, current_user.id, "MODERATE_FEEDBACK", f"Feedback ID {id} approval set to: {is_approved}")
        return feedback
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )
