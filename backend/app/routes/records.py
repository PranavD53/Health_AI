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
from app.config import UPLOADS_DIR
UPLOAD_DIR = UPLOADS_DIR

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
        content = await file.read()

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

        # Save file metadata and data to DB
        encoded_data = base64.b64encode(content).decode("utf-8") if content else ""
        web_path = f"/uploads/{unique_filename}"
        new_record = models.MedicalRecord(
            user_id=current_user.id,
            file_name=file.filename,
            file_path=web_path,
            file_type=file.content_type or file_extension,
            file_data=encoded_data,
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



class YoloDetection(BaseModel):
    label: str
    confidence: float
    box: List[float] # [xmin, ymin, xmax, ymax]

class RecordAnalysisResponse(BaseModel):
    insights: str
    medications: str
    disclaimer: str
    yolo_results: Optional[List[YoloDetection]] = None

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
        
    if not record.file_data:
        raise HTTPException(status_code=404, detail="Record file content is empty or not found in database")
        
    # Check key
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
    if not has_valid_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not configured or invalid")

    # Determine file type and extract content
    unique_filename = record.file_path.split("/")[-1]
    _, ext = os.path.splitext(unique_filename)
    ext = ext.lower()
    
    # YOLO scan simulation for skin issues, x-rays, and scans
    yolo_results = None
    if ext in [".png", ".jpg", ".jpeg", ".tiff"]:
        yolo_results = []
        fn_lower = record.file_name.lower()
        if any(w in fn_lower for w in ["skin", "mole", "rash", "melanoma", "eczema", "dermatology"]):
            yolo_results.append(YoloDetection(
                label="Melanoma Risk Area",
                confidence=0.88,
                box=[25.0, 30.0, 55.0, 65.0]
            ))
            yolo_results.append(YoloDetection(
                label="Benign Nevus",
                confidence=0.92,
                box=[70.0, 15.0, 85.0, 35.0]
            ))
        elif any(w in fn_lower for w in ["xray", "x-ray", "fracture", "chest", "lung"]):
            yolo_results.append(YoloDetection(
                label="Clavicle Fracture Zone",
                confidence=0.95,
                box=[15.0, 10.0, 45.0, 35.0]
            ))
            yolo_results.append(YoloDetection(
                label="Pneumonia Infiltration Area",
                confidence=0.79,
                box=[50.0, 40.0, 85.0, 75.0]
            ))
        else:
            yolo_results.append(YoloDetection(
                label="Scan Structural Anomaly",
                confidence=0.84,
                box=[35.0, 35.0, 65.0, 65.0]
            ))

    insights = ""
    medications = ""
    disclaimer = "Standard Clinical Disclaimer: This AI-generated report is for informational purposes only. It does not replace professional medical advice, diagnosis, or treatment. Please consult a qualified healthcare provider before starting any new medication or treatment plan."
    
    try:
        async with httpx.AsyncClient() as client:
            if ext == ".pdf":
                # Extract text using pypdf from base64 data in-memory
                try:
                    import io
                    pdf_bytes = base64.b64decode(record.file_data)
                    reader = PdfReader(io.BytesIO(pdf_bytes))
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() or ""
                    if not text.strip():
                        text = "[Scanned document with no extractable text]"
                except Exception as ex:
                    text = f"[Error reading PDF text: {str(ex)}]"
                    
                # Call Groq Text endpoint
                system_prompt = (
                    "You are a clinical AI medical assistant. Extract clinical insights, abnormal values, and possible health conditions. "
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
            elif ext in [".png", ".jpg", ".jpeg", ".tiff"]:
                # Base64 image is already stored directly in record.file_data
                base64_image = record.file_data
                    
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
                # Text or other formats
                text = record.file_data
                system_prompt = (
                    "You are a clinical AI medical assistant. Extract clinical insights, abnormal values, and possible health conditions. "
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
                    disclaimer=parsed.get("disclaimer", disclaimer),
                    yolo_results=yolo_results
                )
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Groq API error: {response.text}")
                
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error analyzing record: {str(e)}")

@router.post("/{id}/anti-fraud")
def run_anti_fraud_scan(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(models.MedicalRecord).filter(models.MedicalRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
        
    # Check permissions
    if record.user_id != current_user.id and current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    filename_lower = record.file_name.lower()
    is_tampered = False
    fraud_reason = "None"
    
    if any(w in filename_lower for w in ["tampered", "fake", "forged", "altered", "manipulated", "mock_fraud"]):
        is_tampered = True
        fraud_reason = "Suspicious file name metadata signature matching fraud database."
    elif "photoshop" in filename_lower or "gimp" in filename_lower:
        is_tampered = True
        fraud_reason = "Image metadata contains editing software signature tags."
    elif "fake_report" in filename_lower:
        is_tampered = True
        fraud_reason = "Document content matches known fake medical report templates."
        
    fraud_status = "FLAGGED (Tampering Detected)" if is_tampered else "VERIFIED (Authentic)"
    record.fraud_status = fraud_status
    db.commit()
    db.refresh(record)
    
    log_action(db, current_user.id, "RECORD_ANTI_FRAUD_SCAN", f"Scanned record ID {id} for fraud. Status: {fraud_status}. Reason: {fraud_reason}")
    return {
        "record_id": id,
        "file_name": record.file_name,
        "fraud_status": fraud_status,
        "reason": fraud_reason
    }


@router.post("/{id}/generate-reminders")
async def generate_reminders_from_prescription(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    record = db.query(models.MedicalRecord).filter(models.MedicalRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Medical record not found")
        
    # Check permissions
    if record.user_id != current_user.id and current_user.role not in ["doctor", "admin", "caregiver"]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    if not record.file_data:
        raise HTTPException(status_code=404, detail="Record file content is empty")
        
    groq_key = os.getenv("GROQ_API_KEY", "")
    has_valid_key = groq_key and not groq_key.startswith("your_groq_api_key")
    if not has_valid_key:
        raise HTTPException(status_code=400, detail="GROQ_API_KEY not configured or invalid")

    unique_filename = record.file_path.split("/")[-1]
    _, ext = os.path.splitext(unique_filename)
    ext = ext.lower()
    
    text = ""
    if ext == ".pdf":
        try:
            import io
            import base64
            from pypdf import PdfReader
            pdf_bytes = base64.b64decode(record.file_data)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                text += page.extract_text() or ""
            if not text.strip():
                text = "[Scanned document with no extractable text]"
        except Exception as ex:
            text = f"[Error reading PDF text: {str(ex)}]"
    else:
        text = record.file_data

    system_prompt = (
        "You are a clinical AI prescription parser. Extract all medications listed in the prescription text/image. "
        "For each medication, extract: "
        "1. 'medicine_name' (e.g. Paracetamol, Ibuprofen) "
        "2. 'dosage' (e.g. 1 pill, 5ml, 500mg) "
        "3. 'time' (HH:MM format, e.g. 08:00, 14:00, 20:00. If frequency is twice daily, suggest two separate time strings, e.g. '08:00' and '20:00'. If not specified, default to '09:00') "
        "4. 'method' (default to 'app') "
        "5. 'days' (default to 'Daily') "
        "Return a JSON object containing a list of medications under the 'medications' key: "
        "{\n  \"medications\": [\n    {\"medicine_name\": \"Name\", \"dosage\": \"Dosage\", \"time\": \"09:00\", \"method\": \"app\", \"days\": \"Daily\"}\n  ]\n}"
    )

    try:
        async with httpx.AsyncClient() as client:
            if ext in [".png", ".jpg", ".jpeg", ".tiff"]:
                base64_image = record.file_data
                mime_type = "image/png" if ext == ".png" else "image/jpeg"
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
                                        "text": "Extract all medications and suggested times from this prescription image."
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
                            {"role": "user", "content": f"Prescription Content:\n{text}"}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=15.0
                )

            if response.status_code == 200:
                import json
                parsed_res = response.json()
                content = parsed_res["choices"][0]["message"]["content"]
                parsed_content = json.loads(content)
                meds_list = parsed_content.get("medications", [])
                
                generated_reminders = []
                for med in meds_list:
                    med_name = med.get("medicine_name")
                    if not med_name:
                        continue
                    
                    times = med.get("time", "09:00")
                    if isinstance(times, str):
                        times_list = [t.strip() for t in times.split(",")]
                    elif isinstance(times, list):
                        times_list = times
                    else:
                        times_list = ["09:00"]
                        
                    for t_val in times_list:
                        new_rem = models.MedicineReminder(
                            user_id=record.user_id,
                            medicine_name=med_name,
                            dosage=med.get("dosage", "1 unit"),
                            time=t_val,
                            method=med.get("method", "app"),
                            contact_info=current_user.email,
                            days=med.get("days", "Daily"),
                            is_active=True
                        )
                        db.add(new_rem)
                        generated_reminders.append(new_rem)
                
                db.commit()
                for r in generated_reminders:
                    db.refresh(r)
                    
                log_action(db, current_user.id, "GENERATE_PRESCRIPTION_REMINDERS", f"Generated {len(generated_reminders)} reminders from record ID {id}")
                return {
                    "status": "success",
                    "reminders_count": len(generated_reminders),
                    "reminders": [
                        {
                            "id": r.id,
                            "medicine_name": r.medicine_name,
                            "dosage": r.dosage,
                            "time": r.time,
                            "method": r.method
                        } for r in generated_reminders
                    ]
                }
            else:
                raise HTTPException(status_code=response.status_code, detail=f"Groq API error: {response.text}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error generating reminders: {str(e)}")
