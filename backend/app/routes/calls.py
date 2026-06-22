import os
import time
from app.timezone_helper import datetime
import asyncio
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

class ActiveCallResponse(BaseModel):
    has_active_call: bool
    call_id: Optional[int] = None
    room_id: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    other_party_name: Optional[str] = None
    token: Optional[str] = None
    sfu_url: Optional[str] = None

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

# --- Helpers ---
def get_active_room_id(call: models.CallRecord, db: Session) -> str:
    if call.appointment_id:
        appt = db.query(models.Appointment).filter(models.Appointment.id == call.appointment_id).first()
        if appt:
            siblings = db.query(models.Appointment).filter(
                models.Appointment.doctor_id == appt.doctor_id,
                models.Appointment.date == appt.date,
                models.Appointment.time == appt.time,
                models.Appointment.id != appt.id
            ).all()
            sibling_ids = [s.id for s in siblings]
            if sibling_ids:
                sibling_call = db.query(models.CallRecord).filter(
                    models.CallRecord.appointment_id.in_(sibling_ids),
                    models.CallRecord.status.in_(["INITIATED", "RINGING", "ACCEPTED", "ONGOING"])
                ).order_by(models.CallRecord.id.asc()).first()
                if sibling_call:
                    return sibling_call.room_id
    return call.room_id

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
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either appointment_id or chat_id to start a call."
        )

    # 3. Create or reuse active call record
    if req.appointment_id:
        call = db.query(models.CallRecord).filter(
            models.CallRecord.appointment_id == req.appointment_id,
            models.CallRecord.status.in_(["INITIATED", "RINGING", "ACCEPTED", "ONGOING"])
        ).first()
    else:
        call = db.query(models.CallRecord).filter(
            models.CallRecord.chat_id == req.chat_id,
            models.CallRecord.status.in_(["INITIATED", "RINGING", "ACCEPTED", "ONGOING"])
        ).first()

    if not call:
        # Generate a unique room_id with a timestamp to satisfy DB unique constraints
        if req.appointment_id:
            room_id = f"room_app_{req.appointment_id}_{int(time.time())}"
        else:
            room_id = f"room_chat_{req.chat_id}_{int(time.time())}"

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

    # Resolve shared room name if sibling appointments exist
    active_room_id = get_active_room_id(call, db)

    # 4. Generate short-lived LiveKit token for doctor
    doc_token = generate_livekit_token(
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        room_id=active_room_id,
        identity=str(current_user.id),
        name=doctor_profile.name,
        is_publisher=True
    )

    # 5. Emit call_initiated signaling event to the patient via WebSockets
    signal_data = {
        "event": "call_initiated",
        "data": {
            "call_id": call.id,
            "room_id": active_room_id,
            "doctor_name": doctor_profile.name,
            "appointment_id": req.appointment_id,
            "chat_id": req.chat_id
        }
    }
    await manager.send_personal_json(signal_data, patient_id)

    # 6. Audit log initiation
    log_call_audit(db, call.id, current_user.id, "INITIATE_CALL", request)

    # 7. Create database notification for the patient and send WebSocket alert
    try:
        notif = models.Notification(
            user_id=patient_id,
            message=f"Video consultation with {doctor_profile.name} has started. Click to join.",
            notification_type="meet_started",
            related_id=call.id
        )
        db.add(notif)
        db.commit()
        
        asyncio.create_task(manager.send_personal_json({
            "event": "new_notification"
        }, patient_id))
    except Exception as notif_err:
        logger.error(f"Failed to create call notification: {notif_err}")

    return CallInitiateResponse(
        call_id=call.id,
        room_id=active_room_id,
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

    # Resolve shared room name if sibling appointments exist
    active_room_id = get_active_room_id(call, db)

    patient_token = generate_livekit_token(
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
        room_id=active_room_id,
        identity=str(current_user.id),
        name=patient_name,
        is_publisher=True
    )

    # 5. Emit accepted signaling event to the doctor
    signal_data = {
        "event": "accepted",
        "data": {
            "call_id": call.id,
            "room_id": active_room_id,
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

    if call.status in ["INITIATED", "RINGING"]:
        call.status = "MISSED"
    else:
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


@router.get("/active", response_model=ActiveCallResponse)
async def get_active_call(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Find any active call where the current user is a participant
    call = db.query(models.CallRecord).filter(
        models.CallRecord.status.in_(["INITIATED", "RINGING", "ACCEPTED", "ONGOING"]),
        (models.CallRecord.doctor_id == current_user.id) | (models.CallRecord.patient_id == current_user.id)
    ).order_by(models.CallRecord.id.desc()).first()

    if not call:
        return ActiveCallResponse(has_active_call=False)

    active_room_id = get_active_room_id(call, db)
    
    if current_user.id == call.doctor_id:
        role = "doctor"
        pat = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == call.patient_id).first()
        other_party_name = pat.name if pat else "Patient"
        # Generate doctor LiveKit token
        doc_profile = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        doc_name = doc_profile.name if doc_profile else "Doctor"
        token = generate_livekit_token(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            room_id=active_room_id,
            identity=str(current_user.id),
            name=doc_name,
            is_publisher=True
        )
    else:
        role = "patient"
        doc = db.query(models.Doctor).filter(models.Doctor.user_id == call.doctor_id).first()
        other_party_name = doc.name if doc else "Doctor"
        # Generate patient LiveKit token if accepted or ongoing
        if call.status in ["ACCEPTED", "ONGOING"]:
            pat_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == current_user.id).first()
            pat_name = pat_profile.name if pat_profile else "Patient"
            token = generate_livekit_token(
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_API_SECRET,
                room_id=active_room_id,
                identity=str(current_user.id),
                name=pat_name,
                is_publisher=True
            )
        else:
            token = None

    return ActiveCallResponse(
        has_active_call=True,
        call_id=call.id,
        room_id=active_room_id,
        status=call.status,
        role=role,
        other_party_name=other_party_name,
        token=token,
        sfu_url=LIVEKIT_URL
    )
