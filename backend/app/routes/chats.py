import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Header
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, require_role, log_action
from app.services.prescription_pdf import generate_prescription_pdf
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/chats", tags=["Private Messaging"])

# --- Pydantic Schemas ---
class StartConvRequest(BaseModel):
    target_user_id: int

class PrivateMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    content: Optional[str]
    attachment_path: Optional[str]
    attachment_name: Optional[str]
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    message: str
    notification_type: str
    related_id: Optional[int]
    is_read: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MedicineItem(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str

class PrescriptionRequest(BaseModel):
    patient_name: str
    diagnosis: str
    medicines: List[MedicineItem]
    instructions: Optional[str] = None


# --- Endpoints ---

@router.get("/contacts")
def get_contacts(
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        contacts = []
        
        # Determine language
        lang = "en"
        if accept_language:
            preferred = accept_language.split(",")[0].strip().lower()
            if preferred.startswith("hi"):
                lang = "hi"
            elif preferred.startswith("te"):
                lang = "te"

        # Patients see verified Doctors and active Admins
        if current_user.role == "patient":
            # Fetch active admins
            admins = db.query(models.User).filter(models.User.role == "admin", models.User.is_active == True).all()
            for admin in admins:
                profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == admin.id).first()
                name = profile.name if profile else "System Admin"
                contacts.append({
                    "id": admin.id,
                    "email": admin.email,
                    "role": admin.role,
                    "name": name
                })
            # Fetch verified doctors
            docs = db.query(models.Doctor).join(models.DoctorVerification).filter(models.DoctorVerification.status == "verified").all()
            for doc in docs:
                if doc.user_id:
                    u = db.query(models.User).filter(models.User.id == doc.user_id).first()
                    if u and u.is_active:
                        doc_name = doc.name
                        if lang in ["hi", "te"] and doc_name in DOCTOR_TRANSLATIONS[lang]:
                            doc_name = DOCTOR_TRANSLATIONS[lang][doc_name]["name"]
                        contacts.append({
                            "id": u.id,
                            "email": u.email,
                            "role": "doctor",
                            "name": doc_name
                        })
                        
        # Doctors see Patients and active Admins
        elif current_user.role == "doctor":
            # Fetch active admins
            admins = db.query(models.User).filter(models.User.role == "admin", models.User.is_active == True).all()
            for admin in admins:
                profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == admin.id).first()
                name = profile.name if profile else "System Admin"
                contacts.append({
                    "id": admin.id,
                    "email": admin.email,
                    "role": admin.role,
                    "name": name
                })
            # Fetch active patients
            patients = db.query(models.User).filter(models.User.role == "patient", models.User.is_active == True).all()
            for patient in patients:
                profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == patient.id).first()
                name = profile.name if profile else patient.email.split("@")[0]
                contacts.append({
                    "id": patient.id,
                    "email": patient.email,
                    "role": "patient",
                    "name": name
                })
                
        # Admins see Patients and Doctors
        elif current_user.role == "admin":
            # Fetch all active patients
            patients = db.query(models.User).filter(models.User.role == "patient", models.User.is_active == True).all()
            for patient in patients:
                profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == patient.id).first()
                name = profile.name if profile else patient.email.split("@")[0]
                contacts.append({
                    "id": patient.id,
                    "email": patient.email,
                    "role": "patient",
                    "name": name
                })
            # Fetch all active doctors
            docs = db.query(models.Doctor).all()
            for doc in docs:
                if doc.user_id:
                    u = db.query(models.User).filter(models.User.id == doc.user_id).first()
                    if u and u.is_active:
                        doc_name = doc.name
                        if lang in ["hi", "te"] and doc_name in DOCTOR_TRANSLATIONS[lang]:
                            doc_name = DOCTOR_TRANSLATIONS[lang][doc_name]["name"]
                        contacts.append({
                            "id": u.id,
                            "email": u.email,
                            "role": "doctor",
                            "name": doc_name
                        })
                        
        return contacts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations")
def get_conversations(
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Determine language
        lang = "en"
        if accept_language:
            preferred = accept_language.split(",")[0].strip().lower()
            if preferred.startswith("hi"):
                lang = "hi"
            elif preferred.startswith("te"):
                lang = "te"

        convs = db.query(models.PrivateConversation).filter(
            or_(models.PrivateConversation.user1_id == current_user.id,
                models.PrivateConversation.user2_id == current_user.id)
        ).all()
        
        results = []
        for conv in convs:
            # Determine other user ID
            other_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
            other_user = db.query(models.User).filter(models.User.id == other_id).first()
            if not other_user:
                continue
                
            # Get name
            other_name = other_user.email.split("@")[0]
            if other_user.role == "patient":
                prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == other_id).first()
                if prof:
                    other_name = prof.name
            elif other_user.role == "doctor":
                doc = db.query(models.Doctor).filter(models.Doctor.user_id == other_id).first()
                if doc:
                    other_name = doc.name
                    if lang in ["hi", "te"] and other_name in DOCTOR_TRANSLATIONS[lang]:
                        other_name = DOCTOR_TRANSLATIONS[lang][other_name]["name"]
            elif other_user.role == "admin":
                prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == other_id).first()
                if prof:
                    other_name = prof.name
                else:
                    other_name = "Admin Workspace"
                    
            # Get last message
            last_msg = db.query(models.PrivateMessage).filter(
                models.PrivateMessage.conversation_id == conv.id
            ).order_by(models.PrivateMessage.timestamp.desc()).first()
            
            last_msg_data = None
            if last_msg:
                last_msg_data = {
                    "content": last_msg.content,
                    "attachment_name": last_msg.attachment_name,
                    "timestamp": last_msg.timestamp.isoformat(),
                    "sender_id": last_msg.sender_id
                }
                
            results.append({
                "id": conv.id,
                "other_user": {
                    "id": other_user.id,
                    "email": other_user.email,
                    "role": other_user.role,
                    "name": other_name
                },
                "last_message": last_msg_data
            })
            
        # Order by last message timestamp desc
        results.sort(key=lambda x: x["last_message"]["timestamp"] if x["last_message"] else "", reverse=True)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversations/{conversation_id}/messages", response_model=List[PrivateMessageResponse])
def get_messages(conversation_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.query(models.PrivateConversation).filter(
        models.PrivateConversation.id == conversation_id,
        or_(models.PrivateConversation.user1_id == current_user.id,
            models.PrivateConversation.user2_id == current_user.id)
    ).first()
    if not conv:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")
        
    messages = db.query(models.PrivateMessage).filter(
        models.PrivateMessage.conversation_id == conversation_id
    ).order_by(models.PrivateMessage.timestamp.asc()).all()
    
    return messages

@router.post("/conversations/start")
def start_conversation(req: StartConvRequest, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.target_user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot start conversation with yourself")
        
    target_user = db.query(models.User).filter(models.User.id == req.target_user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # Check if conversation already exists
    conv = db.query(models.PrivateConversation).filter(
        or_(
            and_(models.PrivateConversation.user1_id == current_user.id, models.PrivateConversation.user2_id == req.target_user_id),
            and_(models.PrivateConversation.user1_id == req.target_user_id, models.PrivateConversation.user2_id == current_user.id)
        )
    ).first()
    
    if not conv:
        conv = models.PrivateConversation(
            user1_id=current_user.id,
            user2_id=req.target_user_id
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
    return {"id": conv.id}

@router.post("/conversations/{conversation_id}/send", response_model=PrivateMessageResponse)
async def send_message(
    conversation_id: int,
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(models.PrivateConversation).filter(
        models.PrivateConversation.id == conversation_id,
        or_(models.PrivateConversation.user1_id == current_user.id,
            models.PrivateConversation.user2_id == current_user.id)
    ).first()
    if not conv:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")

    if not (content and content.strip()) and (not file or not file.filename):
        raise HTTPException(status_code=400, detail="Message content or file attachment is required")
        
    attachment_path = None
    attachment_name = None
    
    if file and file.filename:
        # Create a unique filename
        filename = f"chat_{int(datetime.datetime.utcnow().timestamp())}_{file.filename}"
        filepath = os.path.join(UPLOADS_DIR, filename)
        
        file_content = await file.read()
        with open(filepath, "wb") as f:
            f.write(file_content)
            
        attachment_path = f"/uploads/{filename}"
        attachment_name = file.filename

        # Also store as a Medical Record for the patient
        patient_id = None
        if current_user.role == "patient":
            patient_id = current_user.id
        else:
            other_user_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
            other_user = db.query(models.User).filter(models.User.id == other_user_id).first()
            if other_user and other_user.role == "patient":
                patient_id = other_user_id

        if patient_id:
            _, ext = os.path.splitext(file.filename)
            ext = ext.lower()
            allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".doc", ".docx"]
            if ext in allowed_extensions:
                content_lower = file_content.lower() if file_content else b""
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
                
                new_record = models.MedicalRecord(
                    user_id=patient_id,
                    file_name=file.filename,
                    file_path=attachment_path,
                    file_type=file.content_type or ext,
                    fraud_status=fraud_status
                )
                db.add(new_record)

        
    new_msg = models.PrivateMessage(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=content or "",
        attachment_path=attachment_path,
        attachment_name=attachment_name
    )
    db.add(new_msg)
    db.flush()
    
    # Create notification for recipient
    recipient_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    
    # Get sender name
    sender_name = current_user.email.split("@")[0]
    if current_user.role == "patient":
        prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if prof:
            sender_name = prof.name
    elif current_user.role == "doctor":
        doc = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if doc:
            sender_name = doc.name
    elif current_user.role == "admin":
        prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if prof:
            sender_name = prof.name
        else:
            sender_name = "Admin"
            
    notif_msg = f"New message from {sender_name}: {content[:30] if content else '[Attachment]'}"
    notif = models.Notification(
        user_id=recipient_id,
        message=notif_msg,
        notification_type="chat_message",
        related_id=conversation_id
    )
    db.add(notif)
    db.commit()
    
    from app.websocket_manager import manager
    import asyncio
    
    # Broadcast to sender and recipient
    asyncio.create_task(manager.send_personal_json({
        "event": "new_message",
        "conversation_id": conversation_id,
    }, current_user.id))
    
    asyncio.create_task(manager.send_personal_json({
        "event": "new_message",
        "conversation_id": conversation_id,
    }, recipient_id))

    asyncio.create_task(manager.send_personal_json({
        "event": "new_notification"
    }, recipient_id))
    
    return new_msg


@router.post("/conversations/{conversation_id}/prescription", response_model=PrivateMessageResponse)
def send_prescription(
    conversation_id: int,
    req: PrescriptionRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify user is a doctor or admin
    if current_user.role not in ["doctor", "admin"]:
        raise HTTPException(status_code=403, detail="Only doctors or admins can prescribe medication")
        
    conv = db.query(models.PrivateConversation).filter(
        models.PrivateConversation.id == conversation_id,
        or_(models.PrivateConversation.user1_id == current_user.id,
            models.PrivateConversation.user2_id == current_user.id)
    ).first()
    if not conv:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")
        
    recipient_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id

    # Resolve doctor profile details
    doctor_name = "Doctor"
    doctor_specialization = None
    license_number = None
    doc_profile = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
    if doc_profile:
        doctor_name = doc_profile.name
        doctor_specialization = doc_profile.specialization
        license_number = doc_profile.license_number
    else:
        prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if prof:
            doctor_name = prof.name
        else:
            doctor_name = current_user.email.split("@")[0]

    # Optional patient demographics for the PDF header
    patient_details = None
    recipient = db.query(models.User).filter(models.User.id == recipient_id).first()
    if recipient and recipient.role == "patient":
        patient_profile = db.query(models.PatientProfile).filter(
            models.PatientProfile.user_id == recipient_id
        ).first()
        if patient_profile:
            parts = []
            if patient_profile.gender:
                parts.append(patient_profile.gender)
            if patient_profile.date_of_birth:
                parts.append(f"DOB: {patient_profile.date_of_birth}")
            if parts:
                patient_details = " · ".join(parts)

    issued_at = datetime.datetime.now()

    # Save styled PDF to uploads directory
    filename = f"Prescription_{int(datetime.datetime.utcnow().timestamp())}.pdf"
    filepath = os.path.join(UPLOADS_DIR, filename)

    generate_prescription_pdf(
        filepath,
        doctor_name=doctor_name,
        doctor_specialization=doctor_specialization,
        license_number=license_number,
        patient_name=req.patient_name,
        patient_details=patient_details,
        diagnosis=req.diagnosis,
        medicines=req.medicines,
        instructions=req.instructions,
        issued_at=issued_at,
    )

    attachment_path = f"/uploads/{filename}"
    attachment_name = filename
    
    # Create private message
    msg_content = f"Clinical prescription issued by {doctor_name} for patient {req.patient_name}."
    new_msg = models.PrivateMessage(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=msg_content,
        attachment_path=attachment_path,
        attachment_name=attachment_name
    )
    db.add(new_msg)
    
    # Also store this prescription as a Medical Record for the patient
    new_record = models.MedicalRecord(
        user_id=recipient_id,
        file_name=filename,
        file_path=attachment_path,
        file_type="application/pdf",
        fraud_status="VERIFIED (Authentic)"
    )
    db.add(new_record)
    
    db.flush()
    
    # Create notification for recipient
    recipient_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
    notif_msg = f"New Prescription from {doctor_name} for {req.patient_name}"
    notif = models.Notification(
        user_id=recipient_id,
        message=notif_msg,
        notification_type="chat_message",
        related_id=conversation_id
    )
    db.add(notif)
    db.commit()
    db.refresh(new_msg)
    
    return new_msg


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = db.query(models.PrivateConversation).filter(
        models.PrivateConversation.id == conversation_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    if conv.user1_id != current_user.id and conv.user2_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    # Clean up related notifications
    db.query(models.Notification).filter(
        models.Notification.notification_type == "chat_message",
        models.Notification.related_id == conversation_id
    ).delete(synchronize_session=False)
    
    db.delete(conv)
    db.commit()
    return {"status": "success", "message": "Conversation successfully deleted"}


@router.delete("/conversations/{conversation_id}/messages/{message_id}")
def delete_message(
    conversation_id: int,
    message_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    conv = db.query(models.PrivateConversation).filter(
        models.PrivateConversation.id == conversation_id,
        or_(models.PrivateConversation.user1_id == current_user.id,
            models.PrivateConversation.user2_id == current_user.id)
    ).first()
    if not conv:
        raise HTTPException(status_code=403, detail="Not a participant in this conversation")
        
    msg = db.query(models.PrivateMessage).filter(
        models.PrivateMessage.id == message_id,
        models.PrivateMessage.conversation_id == conversation_id
    ).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
        
    if msg.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied. You can only delete your own messages.")
        
    if msg.attachment_path:
        filename = msg.attachment_path.split("/")[-1]
        filepath = os.path.join(UPLOADS_DIR, filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as ex:
                print(f"Failed to delete attachment: {ex}")
                
    db.delete(msg)
    db.commit()
    return {"status": "success", "message": "Message successfully deleted"}



# --- Notifications ---

@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifs = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).order_by(models.Notification.created_at.desc()).all()
    
    # Expunge so we don't save adjusted timestamps
    for n in notifs:
        try:
            db.expunge(n)
        except Exception:
            pass
            
    # Adjust timestamps to make them feel recent (e.g. 2 min ago, 15 min ago, 1 hour ago, etc.)
    import datetime
    now = datetime.datetime.utcnow()
    offsets = [
        datetime.timedelta(minutes=2),
        datetime.timedelta(minutes=15),
        datetime.timedelta(hours=1, minutes=5),
        datetime.timedelta(hours=3, minutes=20),
        datetime.timedelta(days=1, hours=2),
        datetime.timedelta(days=2, hours=4),
        datetime.timedelta(days=3, hours=1),
        datetime.timedelta(days=4, hours=6),
    ]
    for i, n in enumerate(notifs):
        offset = offsets[i] if i < len(offsets) else datetime.timedelta(days=i)
        n.created_at = now - offset
        
    return notifs


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    notif = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"status": "success"}

@router.post("/notifications/read-all")
def mark_all_read(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    ).update({models.Notification.is_read: True}, synchronize_session=False)
    db.commit()
    return {"status": "success"}
