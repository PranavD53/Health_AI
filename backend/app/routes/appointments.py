import datetime
from typing import List, Optional, Union, Any
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action
from app.routes.doctors import translate_doctor

router = APIRouter(prefix="/appointment", tags=["Appointments"])

# --- Pydantic Schemas ---
class AppointmentBook(BaseModel):
    doctor_id: Union[int, str]
    date: str # YYYY-MM-DD
    time: str # HH:MM

class DoctorMinInfo(BaseModel):
    id: int
    name: str
    specialization: str
    location: str

    class Config:
        from_attributes = True

class AppointmentResponse(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    date: str
    time: str
    status: str
    created_at: datetime.datetime
    doctor: Optional[DoctorMinInfo] = None

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("/book", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def book_appointment(
    booking: AppointmentBook,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Resolve doctor_id if it is a string name or a dynamic value
        doctor_id_val = booking.doctor_id
        if isinstance(doctor_id_val, str):
            try:
                doctor_id_val = int(doctor_id_val)
            except ValueError:
                clean_name = doctor_id_val.lower().replace("dr.", "").replace("dr", "").strip()
                doc = db.query(models.Doctor).filter(
                    models.Doctor.name.ilike(f"%{clean_name}%")
                ).first()
                if doc:
                    doctor_id_val = doc.id
                else:
                    doc_by_spec = db.query(models.Doctor).filter(
                        models.Doctor.specialization.ilike(f"%{clean_name}%")
                    ).first()
                    if doc_by_spec:
                        doctor_id_val = doc_by_spec.id
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Doctor '{doctor_id_val}' not found by name or specialization"
                        )

        # Check if doctor exists
        doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id_val).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Doctor not found"
            )

        # Check if doctor is available
        if not doctor.available:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is currently unavailable for booking"
            )

        # Check for scheduling conflicts (same doctor, same date, same time)
        existing_booking = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == doctor_id_val,
            models.Appointment.date == booking.date,
            models.Appointment.time == booking.time,
            models.Appointment.status == "booked"
        ).first()
        if existing_booking:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This time slot is already booked with this doctor"
            )

        # Create booking
        new_appointment = models.Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id_val,
            date=booking.date,
            time=booking.time,
            status="booked"
        )
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)

        # Audit logging
        log_action(db, current_user.id, "BOOK_APPOINTMENT", f"Booked appointment ID {new_appointment.id} with Doctor ID {doctor_id_val} for {booking.date} at {booking.time}")

        return new_appointment
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while booking the appointment: {str(e)}"
        )

@router.get("/my-appointments", response_model=List[AppointmentResponse])
def get_my_appointments(
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if current_user.role == "patient":
            # Patients see their own appointments
            appointments = db.query(models.Appointment).filter(
                models.Appointment.patient_id == current_user.id
            ).all()
        elif current_user.role == "doctor":
            # Find the corresponding Doctor entry using the email
            doctor = db.query(models.Doctor).filter(models.Doctor.contact == current_user.email).first()
            if not doctor:
                # If no matching doctor record, they have no appointments
                return []
            appointments = db.query(models.Appointment).filter(
                models.Appointment.doctor_id == doctor.id
            ).all()
        elif current_user.role in ["admin", "caregiver"]:
            # Admins and Caregivers see all appointments
            appointments = db.query(models.Appointment).all()
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden"
            )

        # Translate doctor info
        lang = "en"
        if accept_language:
            preferred = accept_language.split(",")[0].strip().lower()
            if preferred.startswith("hi"):
                lang = "hi"
            elif preferred.startswith("te"):
                lang = "te"

        res = []
        for appt in appointments:
            appt_resp = AppointmentResponse.from_orm(appt)
            if appt_resp.doctor:
                translate_doctor(appt_resp.doctor, lang)
            res.append(appt_resp)

        return res
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving appointments: {str(e)}"
        )

@router.delete("/cancel/{id}")
def cancel_appointment(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        appointment = db.query(models.Appointment).filter(models.Appointment.id == id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )

        # RBAC Check: Patients can only cancel their own appointments; Doctors/Admins can cancel any
        if current_user.role == "patient" and appointment.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this appointment"
            )

        # Check if already cancelled
        if appointment.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment is already cancelled"
            )

        # Mark as cancelled
        appointment.status = "cancelled"
        db.commit()

        # Audit logging
        log_action(db, current_user.id, "CANCEL_APPOINTMENT", f"Cancelled appointment ID {id}")

        return {"status": "success", "message": "Appointment successfully cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while cancelling the appointment: {str(e)}"
        )

@router.delete("/delete/{id}")
def delete_appointment(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        appointment = db.query(models.Appointment).filter(models.Appointment.id == id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found"
            )

        # Patients can only delete/cancel their own appointments; Doctors/Admins can delete any
        if current_user.role == "patient" and appointment.patient_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this appointment"
            )

        db.delete(appointment)
        db.commit()

        # Audit logging
        log_action(db, current_user.id, "DELETE_APPOINTMENT", f"Deleted appointment ID {id}")

        return {"status": "success", "message": "Appointment successfully deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the appointment: {str(e)}"
        )

