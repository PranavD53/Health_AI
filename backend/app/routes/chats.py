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
from app.routes.doctors import translate_doctor, DOCTOR_TRANSLATIONS

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
def send_message(
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
        
    attachment_path = None
    attachment_name = None
    
    if file:
        # Create uploads directory if not exists
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        uploads_dir = os.path.join(base_dir, "uploads")
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            
        # Create a unique filename
        filename = f"chat_{int(datetime.datetime.utcnow().timestamp())}_{file.filename}"
        filepath = os.path.join(uploads_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(file.file.read())
            
        attachment_path = f"/uploads/{filename}"
        attachment_name = file.filename
        
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
        
    # Get doctor name
    doctor_name = "Doctor"
    doc_profile = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
    if doc_profile:
        doctor_name = doc_profile.name
    else:
        # Fallback to user email/name
        prof = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
        if prof:
            doctor_name = prof.name
        else:
            doctor_name = current_user.email.split("@")[0]

    # Format prescription text
    curr_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meds_str = ""
    for med in req.medicines:
        meds_str += f"- {med.name}: {med.dosage} | {med.frequency} | {med.duration}\n"
        
    prescription_content = f"""=========================================
          CLINICAL PRESCRIPTION
=========================================
Doctor: {doctor_name}
Patient: {req.patient_name}
Date: {curr_date}
Diagnosis: {req.diagnosis}
-----------------------------------------
Prescribed Medications:
{meds_str}
-----------------------------------------
Instructions:
{req.instructions or "Take medications as prescribed."}
=========================================
"""

    # Save to uploads directory
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_dir = os.path.join(base_dir, "uploads")
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        
    filename = f"Prescription_{int(datetime.datetime.utcnow().timestamp())}.txt"
    filepath = os.path.join(uploads_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(prescription_content)
        
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


# --- Notifications ---

@router.get("/notifications", response_model=List[NotificationResponse])
def get_notifications(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    notifs = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id,
        models.Notification.is_read == False
    ).order_by(models.Notification.created_at.desc()).all()
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
