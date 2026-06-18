import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action

router = APIRouter(prefix="/appointment", tags=["Appointments"])

# --- Pydantic Schemas ---
class AppointmentBook(BaseModel):
    doctor_id: int
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
        # Check if doctor exists
        doctor = db.query(models.Doctor).filter(models.Doctor.id == booking.doctor_id).first()
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
            models.Appointment.doctor_id == booking.doctor_id,
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
            doctor_id=booking.doctor_id,
            date=booking.date,
            time=booking.time,
            status="booked"
        )
        db.add(new_appointment)
        db.commit()
        db.refresh(new_appointment)

        # Audit logging
        log_action(db, current_user.id, "BOOK_APPOINTMENT", f"Booked appointment ID {new_appointment.id} with Doctor ID {booking.doctor_id} for {booking.date} at {booking.time}")

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

        return appointments
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
