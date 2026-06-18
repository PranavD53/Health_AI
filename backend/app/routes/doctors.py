import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action

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

    class Config:
        from_attributes = True

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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Doctor)
        if specialization:
            # Case-insensitive partial matching
            query = query.filter(models.Doctor.specialization.ilike(f"%{specialization}%"))
        
        doctors = query.all()
        return doctors
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
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check if doctor profile already exists for this user
        existing = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Doctor profile already exists for this user")

        # Handle license document saving
        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        # Save license document
        doc_ext = license_document.filename.split(".")[-1]
        doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
        doc_path = os.path.join(uploads_dir, doc_filename)
        with open(doc_path, "wb") as f:
            f.write(await license_document.read())
        
        # Save profile picture if provided
        pic_relative_path = None
        if profile_picture:
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_path = os.path.join(uploads_dir, pic_filename)
            with open(pic_path, "wb") as f:
                f.write(await profile_picture.read())
            pic_relative_path = f"/uploads/{pic_filename}"

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
            license_document_path=f"/uploads/{doc_filename}",
            license_number=license_number
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

        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)

        # Update license document if provided
        if license_document:
            doc_ext = license_document.filename.split(".")[-1]
            doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
            doc_path = os.path.join(uploads_dir, doc_filename)
            with open(doc_path, "wb") as f:
                f.write(await license_document.read())
            doctor.license_document_path = f"/uploads/{doc_filename}"
            
            # Since the license has changed, reset verification status to pending!
            verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doctor.id).first()
            if verification:
                verification.status = "pending"
                verification.submitted_at = datetime.datetime.utcnow()
            else:
                verification = models.DoctorVerification(doctor_id=doctor.id, status="pending")
                db.add(verification)
            
            doctor.available = False  # Deactivate doctor until verified again!

        # Update profile picture if provided
        if profile_picture:
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_path = os.path.join(uploads_dir, pic_filename)
            with open(pic_path, "wb") as f:
                f.write(await profile_picture.read())
            doctor.profile_picture = f"/uploads/{pic_filename}"

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
                "license_number": doctor.license_number
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
