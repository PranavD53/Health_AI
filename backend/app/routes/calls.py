import os
import time
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import jwt

from app.database import get_db
from app import models
from app.routes.auth import get_current_user
from app.websocket_manager import manager

router = APIRouter(prefix="/calls", tags=["Video Calls"])

# Get LiveKit credentials from environment
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY", "devkey")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET", "secret")
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://localhost:7880")

# --- Pydantic Schemas ---
class CallInitiateRequest(BaseModel):
    appointment_id: Optional[int] = None
    chat_id: Optional[int] = None

class CallInitiateResponse(BaseModel):
    call_id: int
    room_id: str
    token: str
    sfu_url: str

class CallAcceptResponse(BaseModel):
    call_id: int
    token: str
    sfu_url: str

class CallEndResponse(BaseModel):
    call_id: int
    status: str
    duration_seconds: int

# --- Token Helper ---
def generate_livekit_token(api_key: str, api_secret: str, room_id: str, identity: str, name: str = "", is_publisher: bool = True) -> str:
    now = int(time.time())
    payload = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "exp": now + 600,  # 10 minutes short-lived expiry
        "nbf": now,
        "video": {
            "roomJoin": True,
            "room": room_id,
            "canPublish": is_publisher,
            "canSubscribe": True,
            "canPublishData": True
        }
    }
    return jwt.encode(payload, api_secret, algorithm="HS256")

# --- Audit Logging Helper ---
def log_call_audit(db: Session, call_id: Optional[int], actor_id: Optional[int], action: str, request: Request):
    # Extract client IP and user agent
    ip_address = request.client.host if request.client else "unknown"
    device_info = request.headers.get("user-agent", "unknown")
    
    audit_log = models.VideoCallAuditLog(
        call_id=call_id,
        actor_id=actor_id,
        action=action,
        ip_address=ip_address,
        device_info=device_info
    )
    db.add(audit_log)
    db.commit()

# --- Routes ---

@router.post("/initiate", response_model=CallInitiateResponse)
async def initiate_call(
    req: CallInitiateRequest,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Verify user is a doctor
    if current_user.role != "doctor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors can initiate a video consultation."
        )
        
    doctor_profile = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
    if not doctor_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor profile not found."
        )

    patient_id = None
    room_id = None

    # 2. Validate using appointment or private chat
    if req.appointment_id:
        appointment = db.query(models.Appointment).filter(
            models.Appointment.id == req.appointment_id,
            models.Appointment.doctor_id == doctor_profile.id
        ).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appointment not found or not owned by doctor."
            )
        patient_id = appointment.patient_id
        room_id = f"room_app_{appointment.id}"
    elif req.chat_id:
        conversation = db.query(models.PrivateConversation).filter(
            models.PrivateConversation.id == req.chat_id
        ).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat conversation not found."
            )
        if conversation.user1_id == current_user.id:
            patient_id = conversation.user2_id
        elif conversation.user2_id == current_user.id:
            patient_id = conversation.user1_id
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not part of this conversation."
            )
        room_id = f"room_chat_{conversation.id}_call"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either appointment_id or chat_id to start a call."
        )

    # 3. Create or reuse room record
    call = db.query(models.CallRecord).filter(
        models.CallRecord.room_id == room_id,
        models.CallRecord.status.in_(["INITIATED", "RINGING", "ACCEPTED", "ONGOING"])
    ).first()

    if not call:
        call = models.CallRecord(
            room_id=room_id,
            appointment_id=req.appointment_id,
            chat_id=req.chat_id,
            doctor_id=current_user.id,
            patient_id=patient_id,
            status="INITIATED",
            created_by=current_user.id
        )
        db.add(call)
        db.commit()
        db.refresh(call)

    # 4. Generate short-lived LiveKit token for doctor
    doc_token = generate_livekit_token(
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        room_id=room_id,
        identity=str(current_user.id),
        name=doctor_profile.name,
        is_publisher=True
    )

    # 5. Emit call_initiated signaling event to the patient via WebSockets
    signal_data = {
        "event": "call_initiated",
        "data": {
            "call_id": call.id,
            "room_id": room_id,
            "doctor_name": doctor_profile.name,
            "appointment_id": req.appointment_id,
            "chat_id": req.chat_id
        }
    }
    await manager.send_personal_json(signal_data, patient_id)

    # 6. Audit log initiation
    log_call_audit(db, call.id, current_user.id, "INITIATE_CALL", request)

    return CallInitiateResponse(
        call_id=call.id,
        room_id=room_id,
        token=doc_token,
        sfu_url=LIVEKIT_URL
    )


@router.post("/{call_id}/accept", response_model=CallAcceptResponse)
async def accept_call(
    call_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 1. Retrieve call record
    call = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call record not found."
        )

    # 2. Verify current user is the patient
    if call.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the target patient can accept this call."
        )

    # 3. Update call status
    call.status = "ACCEPTED"
    call.accepted_at = datetime.datetime.utcnow()
    call.started_at = datetime.datetime.utcnow()
    db.commit()

    # 4. Generate token for patient
    patient_name = "Patient"
    patient_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
    if patient_profile:
        patient_name = patient_profile.name

    patient_token = generate_livekit_token(
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        room_id=call.room_id,
        identity=str(current_user.id),
        name=patient_name,
        is_publisher=True
    )

    # 5. Emit accepted signaling event to the doctor
    signal_data = {
        "event": "accepted",
        "data": {
            "call_id": call.id,
            "room_id": call.room_id,
            "patient_name": patient_name
        }
    }
    await manager.send_personal_json(signal_data, call.doctor_id)

    # 6. Audit log acceptance
    log_call_audit(db, call.id, current_user.id, "ACCEPT_CALL", request)

    return CallAcceptResponse(
        call_id=call.id,
        token=patient_token,
        sfu_url=LIVEKIT_URL
    )


@router.post("/{call_id}/reject")
async def reject_call(
    call_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    call = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call record not found."
        )

    if call.patient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the target patient can reject this call."
        )

    call.status = "DECLINED"
    call.ended_at = datetime.datetime.utcnow()
    db.commit()

    # Emit rejected event to doctor
    signal_data = {
        "event": "rejected",
        "data": {
            "call_id": call.id,
            "reason": "Patient declined the call."
        }
    }
    await manager.send_personal_json(signal_data, call.doctor_id)

    log_call_audit(db, call.id, current_user.id, "REJECT_CALL", request)

    return {"status": "DECLINED", "call_id": call.id}


@router.post("/{call_id}/end", response_model=CallEndResponse)
async def end_call(
    call_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    call = db.query(models.CallRecord).filter(models.CallRecord.id == call_id).first()
    if not call:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call record not found."
        )

    if current_user.id not in [call.doctor_id, call.patient_id]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a participant in this call."
        )

    call.status = "COMPLETED"
    call.ended_at = datetime.datetime.utcnow()
    
    # Calculate duration
    if call.started_at:
        duration = (call.ended_at - call.started_at).total_seconds()
        call.duration_seconds = int(duration)
    else:
        call.duration_seconds = 0
        
    db.commit()

    # Send left event to peer
    peer_id = call.patient_id if current_user.id == call.doctor_id else call.doctor_id
    signal_data = {
        "event": "left",
        "data": {
            "call_id": call.id,
            "user_id": current_user.id,
            "role": "doctor" if current_user.id == call.doctor_id else "patient"
        }
    }
    await manager.send_personal_json(signal_data, peer_id)

    log_call_audit(db, call.id, current_user.id, "END_CALL", request)

    return CallEndResponse(
        call_id=call.id,
        status="COMPLETED",
        duration_seconds=call.duration_seconds
    )
