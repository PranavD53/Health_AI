import os
import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.database import get_db
from app import models
from app.routes.auth import get_current_user
from app.services.lab_report_service import process_upload
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/chat/lab-report", tags=["Lab Report Analysis"])

@router.post("/upload")
async def upload_lab_report(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
            
        # Create a unique filename for saving
        filename = f"lab_report_{int(datetime.datetime.utcnow().timestamp())}_{file.filename}"
        filepath = os.path.join(UPLOADS_DIR, filename)
        
        file_bytes = await file.read()
        
        # Save file to disk
        with open(filepath, "wb") as f:
            f.write(file_bytes)
            
        attachment_path = f"/uploads/{filename}"
        
        # Process the uploaded file
        result = await process_upload(db, current_user.id, file_bytes, attachment_path, file.content_type or "")
        
        return result
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during lab report processing: {str(e)}"
        )
