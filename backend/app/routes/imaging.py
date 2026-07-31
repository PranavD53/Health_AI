import os
import datetime
import uuid
import base64
import json
import re
import httpx
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action
from app.routes.records import check_file_status
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/imaging", tags=["Medical Imaging Diagnostics"])

# --- Pydantic Schemas ---
class MedicalImagingResponse(BaseModel):
    id: int
    user_id: int
    file_name: str
    file_path: str
    file_type: str
    scan_type: str
    findings: str
    severity: str
    recommended_specialist: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- JSON parsing helper ---
def clean_json_response(text: str) -> dict:
    text = text.strip()
    # Remove markdown code blocks if present
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return json.loads(text)

# --- Offline Clinical Heuristics Fallback ---
def run_offline_heuristics(scan_type: str, filename: str) -> dict:
    scan_lower = scan_type.lower()
    
    if "skin" in scan_lower or "derma" in scan_lower:
        findings = (
            "Visual inspection indicates localized dermatological lesions. Moderate epidermal erythema "
            "and hyperpigmented borders are observed. The lesion displays distinct asymmetrical margins "
            "and minor scaling. Recommend differential diagnosis for contact dermatitis, eczema, or "
            "localized fungal infection. Patient advised to avoid scratching and apply soothing emollient "
            "(such as Calamine lotion or mild hydrocortisone 1% cream topically twice daily as needed)."
        )
        severity = "Moderate"
        specialist = "dermatology"
    elif "throat" in scan_lower or "redness" in scan_lower or "pharynx" in scan_lower:
        findings = (
            "Posterior pharyngeal wall shows significant vascular congestion and diffuse erythema. "
            "Tonsillar swelling is mild (Grade 1) with no visible purulent exudate or cobblestoning. "
            "Slight uvular inflammation noted. Findings are highly consistent with acute viral pharyngitis. "
            "Recommend warm saline rinses, adequate hydration, and symptomatic monitoring. Suggested OTC medicines: "
            "throat lozenges every 4 hours for irritation, and paracetamol (500mg up to 3 times daily as needed) for mild soreness."
        )
        severity = "Low"
        specialist = "general"
    elif "x-ray" in scan_lower or "xray" in scan_lower or "chest" in scan_lower or "fracture" in scan_lower:
        findings = (
            "Chest/skeletal radiograph analyzed. Lungs demonstrate clear aeration bilateral. "
            "No consolidation, pleural effusion, or active airspace disease detected. Cardiomediastinal "
            "silhouette and hila are within normal limits. Skeletal structures show normal alignment "
            "with no obvious signs of acute fracture or subluxation. Findings suggest normal respiratory "
            "and osseous structures. No prescription medications required. Maintain normal health monitoring."
        )
        severity = "Normal"
        specialist = "general"
    else:
        findings = (
            "Preliminary clinical imaging scan processed. General structural integrity of the target region "
            "appears unremarkable, with no clear anomalies or acute pathology visible. Further specific diagnostic "
            "examinations may be required if clinical symptoms persist. Mild symptoms may be managed with standard "
            "over-the-counter pain relievers or topical emollients as appropriate."
        )
        severity = "Normal"
        specialist = "general"
        
    return {
        "findings": findings,
        "severity": severity,
        "recommended_specialist": specialist
    }

# --- Routes ---

@router.post("/analyze", response_model=MedicalImagingResponse, status_code=status.HTTP_201_CREATED)
async def analyze_imaging(
    file: UploadFile = File(...),
    scan_type: str = Form(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Validate file type is image
        allowed_extensions = [".png", ".jpg", ".jpeg", ".webp", ".gif", ".tiff"]
        _, file_extension = os.path.splitext(file.filename)
        file_extension = file_extension.lower()
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed image extensions: {allowed_extensions}"
            )

        content = await file.read()
        
        # Save file to disk
        unique_filename = f"{uuid.uuid4()}_{file.filename}"
        file_path = os.path.join(UPLOADS_DIR, unique_filename)
        with open(file_path, "wb") as f:
            f.write(content)
        web_path = f"/uploads/{unique_filename}"
        
        # Base64 encode for API payload / DB thumbnail recovery
        encoded_data = base64.b64encode(content).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"

        # Anti-tampering check (informational/logged)
        fraud_status, fraud_reason = check_file_status(content, file.filename, file_extension)

        # Route prediction based on scan category
        scan_lower = scan_type.lower()
        try:
            if "skin" in scan_lower or "derma" in scan_lower:
                from app.services.skin_ai import predict_skin
                pred_res = predict_skin(content)
                analyzed_by = "LaurianeMD/vit-skin-disease (ViT)"
            elif "x-ray" in scan_lower or "xray" in scan_lower or "chest" in scan_lower:
                from app.services.xray_ai import predict_xray
                pred_res = predict_xray(content)
                analyzed_by = "hiroaki-f/my_chest_xray_model (ViT NIH ChestX-ray14)"
            elif "throat" in scan_lower or "redness" in scan_lower or "pharynx" in scan_lower:
                from app.services.throat_ai import predict_throat
                pred_res = predict_throat(content)
                analyzed_by = "Deterministic Feature Heuristic Engine"
            else:
                # Default to skin service if unmapped
                from app.services.skin_ai import predict_skin
                pred_res = predict_skin(content)
                analyzed_by = "LaurianeMD/vit-skin-disease (ViT)"
        except ValueError as val_err:
            # Specific validation / image rejection error (e.g. Throat blur or invalid aspect ratio)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err)
            )
        except RuntimeError as rt_err:
            # Model startup or uninitialized singleton failure
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Diagnostics temporarily unavailable for this tab. Please try again later."
            )
        except Exception as pred_err:
            print(f"Prediction layer error ({scan_type}): {pred_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to analyze image. Please try another image."
            )

        # Extract normalized prediction components
        condition = pred_res.get("condition", "Analyzed Condition")
        confidence = pred_res.get("confidence", 0.0)
        severity = pred_res.get("severity", "Moderate")
        specialist = pred_res.get("specialist", "general")
        recommendation = pred_res.get("recommendation", "")
        top_predictions = pred_res.get("top_predictions", [])
        is_heuristic = pred_res.get("is_heuristic", False)

        # Format findings text and embed structured metadata
        metadata_dict = {
            "top_predictions": top_predictions,
            "is_heuristic": is_heuristic,
            "analyzed_by": analyzed_by,
            "confidence": confidence
        }
        
        findings_text = (
            f"Primary Finding: {condition} (Confidence: {confidence:.1f}%)\n"
            f"Severity Level: {severity}\n"
            f"Clinical Recommendation: {recommendation}\n\n"
            f"[Diagnostic Metadata: {json.dumps(metadata_dict)}]"
        )

        # Save to Database
        new_diagnostic = models.MedicalImagingDiagnostic(
            user_id=current_user.id,
            file_name=file.filename,
            file_path=web_path,
            file_type=mime_type,
            file_data=encoded_data,
            scan_type=scan_type,
            findings=findings_text,
            severity=severity,
            recommended_specialist=specialist
        )
        
        db.add(new_diagnostic)
        db.commit()
        db.refresh(new_diagnostic)

        log_action(
            db,
            current_user.id,
            "ANALYZE_IMAGING",
            f"Analyzed imaging diagnostic scan ID {new_diagnostic.id}. Scan type: {scan_type}. Engine: {analyzed_by}. Severity: {severity}."
        )

        return new_diagnostic
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during image diagnostics analysis: {str(e)}"
        )

@router.get("/my-diagnostics", response_model=List[MedicalImagingResponse])
def get_my_diagnostics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        diagnostics = db.query(models.MedicalImagingDiagnostic).filter(
            models.MedicalImagingDiagnostic.user_id == current_user.id
        ).order_by(models.MedicalImagingDiagnostic.created_at.desc()).all()
        return diagnostics
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving diagnostics: {str(e)}"
        )

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_diagnostic(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        diagnostic = db.query(models.MedicalImagingDiagnostic).filter(
            models.MedicalImagingDiagnostic.id == id
        ).first()
        
        if not diagnostic:
            raise HTTPException(status_code=404, detail="Imaging diagnostic report not found")
            
        # Check permissions (current user must be owner or admin)
        if diagnostic.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden. You do not have permission to delete this diagnostic report."
            )
            
        # Remove file from disk if it exists
        try:
            filename = os.path.basename(diagnostic.file_path)
            full_path = os.path.join(UPLOADS_DIR, filename)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as file_err:
            print(f"Failed to delete diagnostic file on disk: {file_err}")

        db.delete(diagnostic)
        db.commit()
        
        log_action(
            db,
            current_user.id,
            "DELETE_IMAGING",
            f"Deleted imaging diagnostic scan ID {id}."
        )
        return {"status": "success", "message": "Imaging diagnostic report deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the diagnostic report: {str(e)}"
        )
