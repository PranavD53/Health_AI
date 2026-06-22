from app.timezone_helper import datetime
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
    user_id: Optional[int] = None
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

# --- Helper for dynamic timeline offsets ---
def adjust_timestamps_generic(items: list, today_date=None):
    # Using patched datetime from module level
    if not today_date:
        today_date = datetime.date.today()
    now = datetime.datetime.utcnow()
    
    def get_val(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    def set_val(obj, key, val):
        if isinstance(obj, dict):
            obj[key] = val
        else:
            setattr(obj, key, val)

    # Separate old and new
    old_booked = []
    old_past = []
    
    for item in items:
        created_at = get_val(item, "created_at")
        status = get_val(item, "status")
        
        # Check if created_at is naive or timezone-aware
        created_date = created_at.date() if created_at else today_date
        
        if created_date < today_date:
            if status == "booked":
                old_booked.append(item)
            else:
                old_past.append(item)
                
    # Adjust old booked
    old_booked.sort(key=lambda x: get_val(x, "id"))
    for i, item in enumerate(old_booked):
        offset_days = 1 + i * 2
        target_date = today_date + datetime.timedelta(days=offset_days)
        set_val(item, "date", target_date.strftime("%Y-%m-%d"))
        set_val(item, "created_at", now - datetime.timedelta(hours=2 + i))
        
    # Adjust old past
    old_past.sort(key=lambda x: get_val(x, "id"), reverse=True)
    for i, item in enumerate(old_past):
        target_date = today_date - datetime.timedelta(days=i + 1)
        set_val(item, "date", target_date.strftime("%Y-%m-%d"))
        set_val(item, "created_at", now - datetime.timedelta(days=i + 1, hours=i))
        
    return items

# --- Endpoints ---

@router.post("/book", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def book_appointment(
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

        async def notify_doctor_conflict(message_text: str):
            # Resolve doctor user id
            doc_user_id = doctor.user_id
            if not doc_user_id and doctor.contact:
                doc_user = db.query(models.User).filter(models.User.email == doctor.contact).first()
                if doc_user:
                    doc_user_id = doc_user.id
            if doc_user_id:
                try:
                    notif = models.Notification(
                        user_id=doc_user_id,
                        message=message_text,
                        notification_type="general"
                    )
                    db.add(notif)
                    db.commit()
                    
                    from app.websocket_manager import manager
                    await manager.send_personal_json({
                        "event": "new_notification"
                    }, doc_user_id)
                except Exception as ex:
                    db.rollback()
                    print(f"Failed to send conflict notification: {ex}")

        # Check if doctor is available
        if not doctor.available:
            await notify_doctor_conflict(
                f"A patient attempted to book an appointment with you on {booking.date} at {booking.time}, but you are currently marked as unavailable."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor is currently unavailable for booking"
            )

        # Validate clinic hours (08:00 to 20:00)
        if not ("08:00" <= booking.time <= "20:00"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointments must be scheduled during clinic hours (08:00 to 20:00)."
            )

        # Validate booking date is at least 2 days in the future
        try:
            booking_date_obj = datetime.datetime.strptime(booking.date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD."
            )
        
        today = datetime.date.today()
        if booking_date_obj < today + datetime.timedelta(days=2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointments must be booked at least 2 days in advance."
            )

        # Check if booking date falls within approved leave dates
        approved_leave = db.query(models.LeaveRequest).filter(
            models.LeaveRequest.doctor_id == doctor_id_val,
            models.LeaveRequest.status == "approved",
            models.LeaveRequest.start_date <= booking.date,
            models.LeaveRequest.end_date >= booking.date
        ).first()
        if approved_leave:
            await notify_doctor_conflict(
                f"A patient attempted to book an appointment with you on {booking.date} at {booking.time}, which conflicts with your approved leave from {approved_leave.start_date} to {approved_leave.end_date}."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Doctor is on approved leave from {approved_leave.start_date} to {approved_leave.end_date}."
            )

        # Check for scheduling conflicts (same doctor, same date, same time)
        existing_booking = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == doctor_id_val,
            models.Appointment.date == booking.date,
            models.Appointment.time == booking.time,
            models.Appointment.status == "booked"
        ).first()
        if existing_booking:
            await notify_doctor_conflict(
                f"A patient attempted to book an appointment with you on {booking.date} at {booking.time}, which conflicts with an existing booking."
            )
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
        from sqlalchemy.orm import joinedload
        if current_user.role == "patient":
            # Patients see their own appointments
            appointments = db.query(models.Appointment).options(
                joinedload(models.Appointment.doctor)
            ).filter(
                models.Appointment.patient_id == current_user.id
            ).all()
        elif current_user.role == "doctor":
            # Find the corresponding Doctor entry using the email
            doctor = db.query(models.Doctor).filter(models.Doctor.contact == current_user.email).first()
            if not doctor:
                # If no matching doctor record, they have no appointments
                return []
            appointments = db.query(models.Appointment).options(
                joinedload(models.Appointment.doctor)
            ).filter(
                models.Appointment.doctor_id == doctor.id
            ).all()
        elif current_user.role in ["admin", "caregiver"]:
            # Admins and Caregivers see all appointments
            appointments = db.query(models.Appointment).options(
                joinedload(models.Appointment.doctor)
            ).all()
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden"
            )

        # Expunge and adjust timestamps in-place safely
        for appt in appointments:
            _ = appt.doctor  # Force-load lazy relationship in-memory
            try:
                db.expunge(appt)
            except Exception:
                pass
        adjust_timestamps_generic(appointments)

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

@router.post("/complete/{id}")
def complete_appointment(
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

        # Allow patient, doctor, or administrator
        is_patient = appointment.patient_id == current_user.id
        
        is_doctor = False
        doctor = db.query(models.Doctor).filter(models.Doctor.id == appointment.doctor_id).first()
        if doctor and (doctor.user_id == current_user.id or doctor.contact == current_user.email):
            is_doctor = True
            
        is_admin = current_user.role in ["admin", "caregiver"]

        if not (is_patient or is_doctor or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to complete this appointment"
            )

        if appointment.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment is already completed"
            )
            
        if appointment.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot complete a cancelled appointment"
            )

        appointment.status = "completed"
        db.commit()

        # Audit logging
        log_action(db, current_user.id, "COMPLETE_APPOINTMENT", f"Completed appointment ID {id}")

        return {"status": "success", "message": "Appointment successfully completed"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while completing the appointment: {str(e)}"
        )


