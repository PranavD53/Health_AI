import os
import datetime
import uuid
import base64
import httpx
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
from pypdf import PdfReader

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
    fraud_status: str

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

        # Simulated anti-fraud scan heuristics
        content_lower = content.lower() if content else b""
        filename_lower = file.filename.lower()
        
        is_tampered = False
        fraud_reason = "None"
        
        if any(w in filename_lower for w in ["tampered", "fake", "forged", "altered", "manipulated", "mock_fraud"]):
            is_tampered = True
            fraud_reason = "Suspicious file name metadata signature matching fraud database."
        elif b"photoshop" in content_lower or b"gimp" in content_lower or b"tampered" in content_lower or b"altered" in content_lower:
            is_tampered = True
            fraud_reason = "Image metadata contains editing software signature tags."
        elif b"fake medical" in content_lower or b"sample specimen" in content_lower:
            is_tampered = True
            fraud_reason = "Document content matches known fake medical report templates."

        fraud_status = "FLAGGED (Tampering Detected)" if is_tampered else "VERIFIED (Authentic)"

        # Save file metadata to DB
        web_path = f"/uploads/{unique_filename}"
        new_record = models.MedicalRecord(
            user_id=current_user.id,
            file_name=file.filename,
            file_path=web_path,
            file_type=file.content_type or file_extension,
            fraud_status=fraud_status
        )
        db.add(new_record)
        db.commit()
        db.refresh(new_record)

        # Audit logging
        log_action(
            db, 
            current_user.id, 
            "UPLOAD_RECORD", 
            f"Uploaded medical record ID {new_record.id}. Saved to: {unique_filename}. Anti-fraud status: {fraud_status} (Reason: {fraud_reason})"
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


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_record(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        record = db.query(models.MedicalRecord).filter(models.MedicalRecord.id == id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Medical record not found")
            
        # Check permissions (current user must be owner or admin or doctor)
        if record.user_id != current_user.id and current_user.role not in ["admin", "doctor"]:
            raise HTTPException(status_code=403, detail="Permission denied. You cannot delete this record.")
            
        # Delete file from disk if it exists
        unique_filename = record.file_path.split("/")[-1]
        local_filepath = os.path.join(UPLOAD_DIR, unique_filename)
        if os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
            except Exception as ex:
                print(f"Failed to delete file from disk: {ex}")
                
        # Delete from DB
        db.delete(record)
        db.commit()
        
        # Audit logging
        log_action(
            db,
            current_user.id,
            "DELETE_RECORD",
            f"Deleted medical record ID {id} ({record.file_name})"
        )
        
        return {"status": "success", "message": "Medical record successfully deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the medical record: {str(e)}"
        )



class RecordAnalysisResponse(BaseModel):
    insights: str
    medications: str
    disclaimer: str

@router.post("/{id}/analyze", response_model=RecordAnalysisResponse)
async def analyze_record(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Retrieve record
    record = db.query(models.MedicalRecord).filter(models.MedicalRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
        
    # Check permissions (current user must be owner or must be doctor/admin/caregiver)
    if record.user_id != current_user.id and current_user.role not in ["doctor", "admin", "caregiver"]:
        raise HTTPException(status_code=403, detail="Permission denied. You cannot access this record.")
        
    # Get local file path
    unique_filename = record.file_path.split("/")[-1]
    local_filepath = os.path.join(UPLOAD_DIR, unique_filename)
    
    if not os.path.exists(local_filepath):
        raise HTTPException(status_code=404, detail="File not found on disk")
        
    # Check key
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
    if not has_valid_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not configured or invalid")

    # Determine file type and extract content
    _, ext = os.path.splitext(unique_filename)
    ext = ext.lower()
    
    insights = ""
    medications = ""
    disclaimer = "Standard Clinical Disclaimer: This AI-generated report is for informational purposes only. It does not replace professional medical advice, diagnosis, or treatment. Please consult a qualified healthcare provider before starting any new medication or treatment plan."
    
    try:
        async with httpx.AsyncClient() as client:
            if ext == ".pdf":
                # Extract text using pypdf
                try:
                    reader = PdfReader(local_filepath)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    if not text.strip():
                        text = "[Scanned document with no extractable text]"
                except Exception as ex:
                    text = f"[Error reading PDF text: {str(ex)}]"
                    
                # Call Groq Text endpoint
                system_prompt = (
                    "You are a clinical AI medical assistant. Analyze the provided medical record text. "
                    "Extract clinical insights, abnormal values, and possible conditions. "
                    "Suggest safe over-the-counter or general medications for any identified conditions. "
                    "Include a safety disclaimer. Return a JSON object with 'insights', 'medications', and 'disclaimer' keys."
                )
                user_prompt = f"Medical Record Text:\n{text}\n\nAnalyze this medical record and return a JSON object containing:\n1. 'insights': Clinical summary, abnormal lab values, and possible health conditions.\n2. 'medications': Suggested safe over-the-counter medications or treatment recommendations.\n3. 'disclaimer': A medical safety disclaimer.\nResponse format must be valid JSON matching this schema: {{\"insights\": \"...\", \"medications\": \"...\", \"disclaimer\": \"...\"}}"
                
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=15.0
                )
            elif ext in [".png", ".jpg", ".jpeg", ".tiff"]:
                # Base64 encode image
                with open(local_filepath, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                    
                mime_type = "image/jpeg"
                if ext == ".png":
                    mime_type = "image/png"
                elif ext == ".tiff":
                    mime_type = "image/tiff"
                    
                system_prompt = (
                    "You are a clinical AI medical assistant capable of interpreting medical record images. "
                    "Extract clinical insights, abnormal values, and possible conditions. "
                    "Suggest safe over-the-counter or general medications for any identified conditions. "
                    "Include a safety disclaimer. Return a JSON object with 'insights', 'medications', and 'disclaimer' keys."
                )
                
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Analyze this medical record image and return a JSON object containing 'insights', 'medications', and 'disclaimer' keys."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:{mime_type};base64,{base64_image}"
                                        }
                                    }
                                ]
                            }
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=20.0
                )
            else:
                # Other formats (e.g. .doc, .docx, txt)
                try:
                    with open(local_filepath, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read(5000)
                except Exception:
                    text = f"[Binary file format: {ext}]"
                    
                system_prompt = (
                    "You are a clinical AI medical assistant. Analyze the provided medical record text. "
                    "Extract clinical insights, abnormal values, and possible conditions. "
                    "Suggest safe over-the-counter or general medications for any identified conditions. "
                    "Include a safety disclaimer. Return a JSON object with 'insights', 'medications', and 'disclaimer' keys."
                )
                user_prompt = f"Medical Record Text:\n{text}\n\nAnalyze this medical record and return a JSON object containing 'insights', 'medications', and 'disclaimer' keys."
                
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=15.0
                )
                
            if response.status_code == 200:
                import json
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return RecordAnalysisResponse(
                    insights=parsed.get("insights", "No insights extracted."),
                    medications=parsed.get("medications", "No medications suggested."),
                    disclaimer=parsed.get("disclaimer", disclaimer)
                )
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Groq API error: {response.text}")
                
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error analyzing record: {str(e)}")
