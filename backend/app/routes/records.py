import os
import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action

router = APIRouter(prefix="/records", tags=["Medical Records"])

# --- Paths Setup ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# Ensure the upload folder exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Pydantic Schemas ---
class MedicalRecordResponse(BaseModel):
    id: int
    user_id: int
    file_name: str
    file_path: str
    file_type: str
    uploaded_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Endpoints ---

@router.post("/upload", response_model=MedicalRecordResponse, status_code=status.HTTP_201_CREATED)
async def upload_record(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Validate file type
        allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".doc", ".docx"]
        _, file_extension = os.path.splitext(file.filename)
        file_extension = file_extension.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed extensions: {allowed_extensions}"
            )

        # Generate unique filename to avoid collision
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        dest_path = os.path.join(UPLOAD_DIR, unique_filename)

        # Save file to disk
        with open(dest_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Save file metadata to DB
        web_path = f"/uploads/{unique_filename}"
        new_record = models.MedicalRecord(
            user_id=current_user.id,
            file_name=file.filename,
            file_path=web_path,
            file_type=file.content_type or file_extension
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)

        # Audit logging
        log_action(
            db, 
            current_user.id, 
            "UPLOAD_RECORD", 
            f"Uploaded medical record ID {new_record.id}. Saved to: {unique_filename}"
        )

        return new_record
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while uploading the file: {str(e)}"
        )

@router.get("/my-records", response_model=List[MedicalRecordResponse])
def get_my_records(
    patient_user_id: Optional[int] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # RBAC Check: Patients can only retrieve their own records; Doctor, Admin, Caregiver can view others
        if patient_user_id is not None and patient_user_id != current_user.id:
            if current_user.role not in ["doctor", "admin", "caregiver"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access forbidden. You do not have permission to view other patients' records."
                )
            target_user_id = patient_user_id
        else:
            target_user_id = current_user.id

        records = db.query(models.MedicalRecord).filter(
            models.MedicalRecord.user_id == target_user_id
        ).order_by(models.MedicalRecord.uploaded_at.desc()).all()
        
        return records
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving medical records: {str(e)}"
        )
