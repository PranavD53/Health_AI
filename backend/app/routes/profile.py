import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, require_role, log_action

router = APIRouter(prefix="/profile", tags=["Patient Profile"])

# --- Pydantic Schemas ---
class ProfileCreate(BaseModel):
    name: str
    date_of_birth: Optional[str] = None # YYYY-MM-DD
    gender: Optional[str] = None
    height: Optional[float] = None # in cm
    weight: Optional[float] = None # in kg
    allergies: Optional[str] = None
    existing_conditions: Optional[str] = None
    address: Optional[str] = None

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    allergies: Optional[str] = None
    existing_conditions: Optional[str] = None
    address: Optional[str] = None

class ProfileResponse(BaseModel):
    id: int
    user_id: int
    name: str
    date_of_birth: Optional[str]
    gender: Optional[str]
    height: Optional[float]
    weight: Optional[float]
    allergies: Optional[str]
    existing_conditions: Optional[str]
    address: Optional[str] = None
    updated_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(profile_data: ProfileCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Check if profile already exists
        existing_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile already exists. Use PUT to update it."
            )

        new_profile = models.PatientProfile(
            user_id=current_user.id,
            name=profile_data.name,
            date_of_birth=profile_data.date_of_birth,
            gender=profile_data.gender,
            height=profile_data.height,
            weight=profile_data.weight,
            allergies=profile_data.allergies,
            existing_conditions=profile_data.existing_conditions,
            address=profile_data.address
        )
        db.add(new_profile)
        db.commit()
        db.refresh(new_profile)

        # Audit logging
        log_action(db, current_user.id, "CREATE_PROFILE", f"Created profile for user ID {current_user.id}")

        return new_profile
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the profile: {str(e)}"
        )

@router.get("", response_model=ProfileResponse)
def get_profile(
    patient_user_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # If accessing someone else's profile
        if patient_user_id is not None and patient_user_id != current_user.id:
            # Check if user has permission (doctor, admin, caregiver)
            if current_user.role not in ["doctor", "admin", "caregiver"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden. You do not have permission to view other patient profiles."
                )
            target_user_id = patient_user_id
        else:
            target_user_id = current_user.id

        profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == target_user_id).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        return profile
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the profile: {str(e)}"
        )

@router.put("", response_model=ProfileResponse)
def update_profile(
    profile_data: ProfileUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found. Create a profile first."
            )

        # Update fields
        update_data = profile_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)

        profile.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(profile)

        # Audit logging
        log_action(db, current_user.id, "UPDATE_PROFILE", f"Updated profile fields: {list(update_data.keys())}")

        return profile
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the profile: {str(e)}"
        )
