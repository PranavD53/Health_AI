import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/doctors", tags=["Doctors"])

# --- Pydantic Schemas ---
class DoctorResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    specialization: str
    location: str
    experience_years: int
    available: bool
    contact: str
    address: Optional[str] = None
    profile_picture: Optional[str] = None
    license_document_path: Optional[str] = None
    license_number: Optional[str] = None
    rating_average: Optional[float] = 4.9
    review_count: Optional[int] = 0

    class Config:
        from_attributes = True

# --- Translation Support ---
DOCTOR_TRANSLATIONS = {
    "hi": {
        "Dr. Alice Smith": {
            "name": "डॉ. एलिस स्मिथ",
            "specialization": "हृदय रोग विज्ञान (Cardiology)",
            "location": "भवन A, कमरा 102, सिटी जनरल अस्पताल"
        },
        "Dr. Bob Johnson": {
            "name": "डॉ. बॉब जॉनसन",
            "specialization": "त्वचा विज्ञान (Dermatology)",
            "location": "स्किन केयर क्लिनिक, 45 पार्क एवेन्यू"
        },
        "Dr. Charlie Brown": {
            "name": "डॉ. चार्ली ब्राउन",
            "specialization": "सामान्य चिकित्सा (General Medicine)",
            "location": "सुइट 300, मेडिकल प्लाजा"
        },
        "Dr. Diana Prince": {
            "name": "डॉ. डायना प्रिंस",
            "specialization": "न्यूरोलॉजी (Neurology)",
            "location": "न्यूरोसाइंस सेंटर, 88 ग्रैंड सेंट"
        },
        "Dr. Evan Wright": {
            "name": "डॉ. एवन राइट",
            "specialization": "बाल रोग विज्ञान (Pediatrics)",
            "location": "चिल्ड्रन क्लिनिक, 12 मेपल सेंट"
        }
    },
    "te": {
        "Dr. Alice Smith": {
            "name": "డా. ఆలిస్ స్మిత్",
            "specialization": "గుండె జబ్బుల నిపుణులు (Cardiology)",
            "location": "బిల్డింగ్ A, రూమ్ 102, సిటీ జనరల్ హాస్పిటల్"
        },
        "Dr. Bob Johnson": {
            "name": "డా. బాబ్ జాన్సన్",
            "specialization": "చర్మవ్యాధి నిపుణులు (Dermatology)",
            "location": "స్కిన్ కేర్ క్లినిక్, 45 పార్క్ అవెన్యూ"
        },
        "Dr. Charlie Brown": {
            "name": "డా. చార్లీ బ్రౌన్",
            "specialization": "జనరల్ మెడిసిన్ (General Medicine)",
            "location": "సూట్ 300, మెడికల్ ప్లాజా"
        },
        "Dr. Diana Prince": {
            "name": "డా. డయానా ప్రిన్స్",
            "specialization": "నరాల వ్యాధుల నిపుణులు (Neurology)",
            "location": "న్యూరోసైన్స్ సెంటర్, 88 గ్రాండ్ సెయింట్"
        },
        "Dr. Evan Wright": {
            "name": "డా. ఇవాన్ రైట్",
            "specialization": "పిల్లల వైద్య నిపుణులు (Pediatrics)",
            "location": "చిల్డ్రన్స్ క్లినిక్, 12 మేపుల్ సెయింట్"
        }
    }
}

def translate_doctor(doc_obj, lang: str):
    if not lang or lang not in ["hi", "te"]:
        return doc_obj
    
    is_dict = isinstance(doc_obj, dict)
    name = doc_obj.get("name") if is_dict else getattr(doc_obj, "name", None)
    
    if name and name in DOCTOR_TRANSLATIONS[lang]:
        trans = DOCTOR_TRANSLATIONS[lang][name]
        if is_dict:
            doc_obj["name"] = trans["name"]
            doc_obj["specialization"] = trans["specialization"]
            if "location" in doc_obj:
                doc_obj["location"] = trans["location"]
        else:
            doc_obj.name = trans["name"]
            doc_obj.specialization = trans["specialization"]
            if hasattr(doc_obj, "location") and doc_obj.location is not None:
                doc_obj.location = trans["location"]
    return doc_obj

# --- Database Seeding Helper ---
def seed_doctors(db: Session):
    count = db.query(models.Doctor).count()
    if count == 0:
        sample_doctors = [
            models.Doctor(
                name="Dr. Alice Smith",
                specialization="Cardiology",
                location="Building A, Room 102, City General Hospital",
                experience_years=15,
                available=True,
                contact="alice.smith@hospital.com",
                license_number="MD-ALICE-15"
            ),
            models.Doctor(
                name="Dr. Bob Johnson",
                specialization="Dermatology",
                location="Skin Care Clinic, 45 Park Ave",
                experience_years=8,
                available=True,
                contact="bob.johnson@skincare.com",
                license_number="MD-BOB-8"
            ),
            models.Doctor(
                name="Dr. Charlie Brown",
                specialization="General Medicine",
                location="Suite 300, Medical Plaza",
                experience_years=12,
                available=True,
                contact="charlie.brown@medplaza.com",
                license_number="MD-CHARLIE-12"
            ),
            models.Doctor(
                name="Dr. Diana Prince",
                specialization="Neurology",
                location="Neuroscience Center, 88 Grand St",
                experience_years=20,
                available=True,
                contact="diana.prince@neurocenter.com",
                license_number="MD-DIANA-20"
            ),
            models.Doctor(
                name="Dr. Evan Wright",
                specialization="Pediatrics",
                location="Children's Clinic, 12 Maple St",
                experience_years=10,
                available=False, # Seed one as unavailable
                contact="evan.wright@childrens.com",
                license_number="MD-EVAN-10"
            )
        ]
        db.add_all(sample_doctors)
        db.commit()
        print("Doctor table successfully seeded with sample records.")

# --- Endpoints ---

@router.get("", response_model=List[DoctorResponse])
def get_doctors(
    specialization: Optional[str] = None,
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Doctor)
        if specialization:
            # Case-insensitive partial matching
            query = query.filter(models.Doctor.specialization.ilike(f"%{specialization}%"))
        
        doctors = query.all()
        
        # Translate dynamically
        lang = "en"
        if accept_language:
            preferred = accept_language.split(",")[0].strip().lower()
            if preferred.startswith("hi"):
                lang = "hi"
            elif preferred.startswith("te"):
                lang = "te"

        res = []
        for d in doctors:
            d_resp = DoctorResponse.from_orm(d)
            translate_doctor(d_resp, lang)
            
            # Compute average rating & review count dynamically
            approved_feedbacks = [f for f in d.feedbacks if f.is_approved]
            if approved_feedbacks:
                d_resp.rating_average = round(sum(f.rating_doctor for f in approved_feedbacks) / len(approved_feedbacks), 1)
                d_resp.review_count = len(approved_feedbacks)
            else:
                d_resp.rating_average = 4.9 # Seed fallback
                d_resp.review_count = 0
                
            res.append(d_resp)
            
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the doctors list: {str(e)}"
        )

@router.post("/register")
async def register_doctor(
    name: str = Form(...),
    specialization: str = Form(...),
    location: str = Form(...),
    experience_years: int = Form(...),
    contact: str = Form(...),
    address: Optional[str] = Form(None),
    license_number: str = Form(...),
    license_document: UploadFile = File(...),
    profile_picture: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check if doctor profile already exists for this user
        existing = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Doctor profile already exists for this user")

        # Handle license document saving (in-memory)
        import base64
        doc_ext = license_document.filename.split(".")[-1]
        doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
        doc_bytes = await license_document.read()
        
        # Save profile picture if provided (in-memory)
        pic_relative_path = None
        pic_encoded = None
        if profile_picture:
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_bytes = await profile_picture.read()
            pic_relative_path = f"/uploads/{pic_filename}"
            pic_encoded = base64.b64encode(pic_bytes).decode("utf-8")

        # Ensure doctor name starts with "Dr." prefix
        name_stripped = name.strip()
        if not name_stripped.lower().startswith("dr.") and not name_stripped.lower().startswith("dr "):
            name = f"Dr. {name_stripped}"
        else:
            name = name_stripped

        # Create Doctor entry
        new_doc = models.Doctor(
            user_id=current_user.id,
            name=name,
            specialization=specialization,
            location=location,
            experience_years=experience_years,
            contact=contact,
            address=address,
            available=False, # Must be verified/approved by admin first
            profile_picture=pic_relative_path,
            profile_picture_data=pic_encoded,
            license_document_path=f"/uploads/{doc_filename}",
            license_document_data=base64.b64encode(doc_bytes).decode("utf-8"),
            license_number=license_number,
            latitude=latitude,
            longitude=longitude
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Create DoctorVerification entry
        verification = models.DoctorVerification(
            doctor_id=new_doc.id,
            status="pending"
        )
        db.add(verification)
        db.commit()

        # Log action
        log_action(db, current_user.id, "REGISTER_DOCTOR_PROFILE", f"Doctor {name} profile registered under user {current_user.email}")

        return {
            "status": "success",
            "message": "Doctor profile registered successfully and is pending admin approval.",
            "doctor_id": new_doc.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during doctor registration: {str(e)}"
        )

@router.put("/profile")
async def update_doctor_profile(
    name: Optional[str] = Form(None),
    specialization: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    experience_years: Optional[int] = Form(None),
    contact: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    license_number: Optional[str] = Form(None),
    license_document: Optional[UploadFile] = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")

        # Update text fields if provided
        if name is not None:
            doctor.name = name
        if specialization is not None:
            doctor.specialization = specialization
        if location is not None:
            doctor.location = location
        if experience_years is not None:
            doctor.experience_years = experience_years
        if contact is not None:
            doctor.contact = contact
        if address is not None:
            doctor.address = address
        if license_number is not None:
            doctor.license_number = license_number
        if latitude is not None:
            doctor.latitude = latitude
        if longitude is not None:
            doctor.longitude = longitude

        # Update license document if provided (in-memory)
        if license_document:
            import base64
            doc_ext = license_document.filename.split(".")[-1]
            doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
            doc_bytes = await license_document.read()
            doctor.license_document_path = f"/uploads/{doc_filename}"
            doctor.license_document_data = base64.b64encode(doc_bytes).decode("utf-8")
            
            # Since the license has changed, reset verification status to pending!
            verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doctor.id).first()
            if verification:
                verification.status = "pending"
                verification.submitted_at = datetime.datetime.utcnow()
            else:
                verification = models.DoctorVerification(doctor_id=doctor.id, status="pending")
                db.add(verification)
            
            doctor.available = False  # Deactivate doctor until verified again!

        # Update profile picture if provided (in-memory)
        if profile_picture:
            import base64
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_bytes = await profile_picture.read()
            doctor.profile_picture = f"/uploads/{pic_filename}"
            doctor.profile_picture_data = base64.b64encode(pic_bytes).decode("utf-8")

        db.commit()
        db.refresh(doctor)

        log_action(db, current_user.id, "UPDATE_DOCTOR_PROFILE", f"Doctor {doctor.name} updated profile. License updated: {license_document is not None}")
        return {
            "status": "success",
            "message": "Doctor profile updated successfully.",
            "doctor": {
                "name": doctor.name,
                "specialization": doctor.specialization,
                "location": doctor.location,
                "available": doctor.available,
                "profile_picture": doctor.profile_picture,
                "license_document_path": doctor.license_document_path,
                "license_number": doctor.license_number,
                "latitude": doctor.latitude,
                "longitude": doctor.longitude
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- Leave Requests ---
class LeaveRequestCreate(BaseModel):
    start_date: str # YYYY-MM-DD
    end_date: str # YYYY-MM-DD
    reason: Optional[str] = None

@router.post("/leave-request")
def create_leave_request(
    data: LeaveRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
        
    new_request = models.LeaveRequest(
        doctor_id=doctor.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    log_action(db, current_user.id, "LEAVE_REQUEST_SUBMITTED", f"Doctor {doctor.name} requested leave from {data.start_date} to {data.end_date}")
    return {"status": "success", "message": "Leave request submitted successfully", "request_id": new_request.id}

@router.get("/leave-requests")
def get_leave_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can view leave requests")
        
    requests = db.query(models.LeaveRequest).all()
    res = []
    for r in requests:
        res.append({
            "id": r.id,
            "doctor_id": r.doctor_id,
            "doctor_name": r.doctor.name,
            "specialization": r.doctor.specialization,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at
        })
    return res

@router.post("/leave-request/{id}/approve")
def approve_leave_request(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can approve leave requests")
        
    req = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    req.status = "approved"
    
    # Set doctor as unavailable
    doctor = db.query(models.Doctor).filter(models.Doctor.id == req.doctor_id).first()
    if doctor:
        doctor.available = False
        
    # Notify doctor
    doctor_notif = models.Notification(
        user_id=doctor.user_id,
        message=f"Your leave request from {req.start_date} to {req.end_date} has been APPROVED by the administrator.",
        notification_type="general"
    )
    db.add(doctor_notif)
    
    db.commit()
    log_action(db, current_user.id, "LEAVE_REQUEST_APPROVED", f"Leave request {id} approved for doctor {doctor.name if doctor else 'Unknown'}")
    return {"status": "success", "message": "Leave request approved successfully"}

@router.post("/leave-request/{id}/reject")
def reject_leave_request(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can reject leave requests")
        
    req = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    req.status = "rejected"
    
    # Notify doctor
    doctor = db.query(models.Doctor).filter(models.Doctor.id == req.doctor_id).first()
    if doctor:
        doctor_notif = models.Notification(
            user_id=doctor.user_id,
            message=f"Your leave request from {req.start_date} to {req.end_date} has been REJECTED by the administrator.",
            notification_type="general"
        )
        db.add(doctor_notif)
        
    db.commit()
    log_action(db, current_user.id, "LEAVE_REQUEST_REJECTED", f"Leave request {id} rejected for doctor {doctor.name if doctor else 'Unknown'}")
    return {"status": "success", "message": "Leave request rejected successfully"}

# --- Urgent Surgery Replacement ---
@router.post("/{doctor_id}/trigger-surgery-replacement")
def trigger_surgery_replacement(
    doctor_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    # Check permissions (doctor themselves or admin)
    if current_user.role != "admin" and doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to trigger surgery replacement for this doctor")
        
    # Fetch all booked appointments of this doctor
    appointments = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.status == "booked"
    ).all()
    
    # Find other doctors in the same department
    other_doctors = db.query(models.Doctor).filter(
        models.Doctor.specialization == doctor.specialization,
        models.Doctor.id != doctor_id,
        models.Doctor.available == True
    ).all()
    
    reassigned_count = 0
    not_reassigned_count = 0
    
    for appt in appointments:
        if other_doctors:
            new_doc = other_doctors[reassigned_count % len(other_doctors)]
            old_doc_name = doctor.name
            appt.doctor_id = new_doc.id
            
            # Create notifications
            patient_notif = models.Notification(
                user_id=appt.patient_id,
                message=f"Your appointment on {appt.date} at {appt.time} has been reassigned to {new_doc.name} because {old_doc_name} has an urgent surgery.",
                notification_type="general"
            )
            new_doc_notif = models.Notification(
                user_id=new_doc.user_id,
                message=f"You have been assigned a new appointment on {appt.date} at {appt.time} (reassigned from {old_doc_name} due to urgent surgery).",
                notification_type="general"
            )
            db.add(patient_notif)
            db.add(new_doc_notif)
            reassigned_count += 1
        else:
            appt.status = "pending_reschedule"
            patient_notif = models.Notification(
                user_id=appt.patient_id,
                message=f"Your appointment with {doctor.name} on {appt.date} at {appt.time} is pending reschedule as the doctor has an urgent surgery and no replacement is available.",
                notification_type="general"
            )
            db.add(patient_notif)
            not_reassigned_count += 1
            
    db.commit()
    log_action(db, current_user.id, "SURGERY_REPLACEMENT_TRIGGERED", f"Doctor {doctor.name} triggered surgery replacement. Reassigned: {reassigned_count}, Rescheduled: {not_reassigned_count}")
    return {
        "status": "success",
        "reassigned": reassigned_count,
        "pending_reschedule": not_reassigned_count
    }
