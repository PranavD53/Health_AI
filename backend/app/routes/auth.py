import os
import datetime
import random
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
import bcrypt
import httpx
from pydantic import BaseModel, EmailStr

# Load configurations by specifically locating the .env file relative to this module
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from app.database import get_db
from app import models

# Load environment configs
SECRET_KEY = os.getenv("SECRET_KEY", "healthcare_secret_key_123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))

# Password hashing
# Hashing done directly via bcrypt package

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Pydantic Schemas ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str = "patient" # patient, doctor, admin, caregiver

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenRefresh(BaseModel):
    refresh_token: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    role: str
    is_verified: bool

class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    is_verified: bool
    admin_requested: bool = False
    has_admin_permission: bool = False
    base_role: str = "patient"
    doctor_profile_id: Optional[int] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- Helpers ---
def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(days=7) # Refresh token lasts 7 days
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def log_action(db: Session, user_id: Optional[int], action: str, details: str):
    try:
        db_log = models.AuditLog(user_id=user_id, action=action, details=details)
        db.add(db_log)
        db.commit()
    except Exception as e:
        db.rollback()
        # Fallback print if DB log fails
        print(f"Failed to write audit log: {e}")

# --- Security Dependencies ---
def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None:
        raise credentials_exception
    
    # Just-in-time repair for legacy doctors/admins with default base_role = 'patient'
    if user.base_role == "patient" and (user.role in ("doctor", "admin") or user.has_admin_permission):
        is_doctor = db.query(models.Doctor).filter(models.Doctor.user_id == user.id).first() is not None
        if is_doctor or user.has_admin_permission:
            user.base_role = "doctor" if is_doctor else "admin"
            db.commit()

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return user

def require_role(allowed_roles: list[str]):
    def role_dependency(current_user: models.User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted. Required roles: {allowed_roles}"
            )
        return current_user
    return role_dependency

def send_via_brevo(to_email: str, subject: str, html_content: str, text_content: Optional[str] = None, sender_name: str = "Health AI Assistant"):
    token = os.getenv("BREVO_API_KEY")
    if token:
        token = token.strip().strip("\"'")
    if not token:
        raise ValueError("BREVO_API_KEY is not configured")
        
    sender_email = os.getenv("BREVO_SENDER_EMAIL") or os.getenv("GMAIL_USER")
    if sender_email:
        sender_email = sender_email.strip().strip("\"'")
    if not sender_email:
        raise ValueError("Sender email is not configured")
        
    s_name = os.getenv("BREVO_SENDER_NAME", sender_name)
    if s_name:
        s_name = s_name.strip().strip("\"'")
        
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": token,
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    
    body = {
        "sender": {"name": s_name, "email": sender_email},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content
    }
    if text_content:
        body["textContent"] = text_content
        
    with httpx.Client() as client:
        response = client.post(url, headers=headers, json=body, timeout=10.0)
        data = response.json()
        if response.status_code >= 400:
            raise Exception(data.get("message") or f"Brevo responded with status {response.status_code}")
        print(f"[Brevo] Email sent: {data}")
        return data

def send_otp_email(email: str, otp: str):
    subject = "Your OTP Code for HealthAI Verification"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
        <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 8px;">
            <h2 style="color: #00355f; text-align: center;">HealthAI Verification</h2>
            <p>Hello,</p>
            <p>Thank you for registering. Please use the following One-Time Password (OTP) to complete your verification and access your dashboard:</p>
            <div style="font-size: 24px; font-weight: bold; text-align: center; margin: 20px 0; padding: 10px; background-color: #f0f8ff; color: #006970; letter-spacing: 4px; border-radius: 4px;">
                {otp}
            </div>
            <p>This code is valid for 10 minutes. If you did not request this verification, please ignore this email.</p>
            <br/>
            <p>Best regards,</p>
            <p><strong>HealthAI Team</strong></p>
        </div>
    </body>
    </html>
    """
    text_content = f"Your HealthAI verification OTP is: {otp}"
    
    try:
        send_via_brevo(email, subject, html_content, text_content)
        print(f"Brevo email sent to {email} successfully.")
    except Exception as e:
        print(f"Brevo email sending exception: {e}")
        print(f"\n==========================================")
        print(f"OTP FOR {email}: {otp} (FAILED TO SEND VIA BREVO: {str(e)})")
        print(f"==========================================\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send email via Brevo: {str(e)}"
        )

# --- Endpoints ---

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    try:
        # Check if user already exists
        existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )

        # Validate role
        valid_roles = ["patient", "doctor", "admin", "caregiver"]
        if user_data.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of {valid_roles}"
            )

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        otp_code = f"{random.randint(100000, 999999)}"
        new_user = models.User(
            email=user_data.email,
            password=hashed_password,
            role=user_data.role,
            base_role=user_data.role,
            has_admin_permission=False,
            is_active=True,
            otp=otp_code,
            is_verified=False
        )
        db.add(new_user)
        db.flush()

        # Send OTP
        send_otp_email(new_user.email, otp_code)

        db.commit()
        db.refresh(new_user)

        # Audit logging
        log_action(db, new_user.id, "REGISTER", f"User registered with role: {new_user.role}. OTP generated.")

        return new_user
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during registration: {str(e)}"
        )

@router.post("/login", response_model=Token)
def login(login_data: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == login_data.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User is not registered",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is deactivated"
            )

        # Generate tokens
        access_token = create_access_token(data={"sub": user.email, "role": user.role})
        refresh_token = create_refresh_token(data={"sub": user.email})

        # Audit logging
        log_action(db, user.id, "LOGIN", f"User logged in successfully")

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user.role,
            "is_verified": user.is_verified
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during login: {str(e)}"
        )

@router.post("/refresh", response_model=Token)
def refresh(refresh_data: TokenRefresh, db: Session = Depends(get_db)):
    try:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
        )
        try:
            payload = jwt.decode(refresh_data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            email: str = payload.get("sub")
            token_type: str = payload.get("type")
            if email is None or token_type != "refresh":
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        user = db.query(models.User).filter(models.User.email == email).first()
        if not user or not user.is_active:
            raise credentials_exception

        # Generate new tokens
        access_token = create_access_token(data={"sub": user.email, "role": user.role})
        new_refresh_token = create_refresh_token(data={"sub": user.email})

        # Audit logging
        log_action(db, user.id, "TOKEN_REFRESH", f"User refreshed access token")

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "role": user.role,
            "is_verified": user.is_verified
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during token refresh: {str(e)}"
        )

@router.post("/logout")
def logout(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Audit logging
        log_action(db, current_user.id, "LOGOUT", "User logged out")
        return {"status": "success", "message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during logout: {str(e)}"
        )

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str

@router.post("/verify-otp", response_model=Token)
def verify_otp(data: VerifyOTPRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == data.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.otp:
            raise HTTPException(status_code=400, detail="No active verification code found")

        if user.otp == data.otp:
            user.is_verified = True
            user.otp = None  # clear OTP
            db.commit()
            
            # Log action
            log_action(db, user.id, "VERIFY_OTP", f"User {user.email} verified successfully")
            
            # Generate tokens
            access_token = create_access_token(data={"sub": user.email, "role": user.role})
            refresh_token = create_refresh_token(data={"sub": user.email})
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "role": user.role,
                "is_verified": True
            }
        else:
            raise HTTPException(status_code=400, detail="Invalid OTP code")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class ResendOTPRequest(BaseModel):
    email: EmailStr

@router.post("/resend-otp")
def resend_otp(data: ResendOTPRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == data.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_verified:
            raise HTTPException(status_code=400, detail="User email is already verified")
            
        otp_code = user.otp if user.otp else f"{random.randint(100000, 999999)}"
        user.otp = otp_code
        db.flush()
        
        send_otp_email(user.email, otp_code)
        db.commit()
        log_action(db, user.id, "RESEND_OTP", f"Resent verification OTP code to user {user.email}")
        return {"status": "success", "message": "Verification code has been resent."}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

class ToggleStatusRequest(BaseModel):
    user_id: int
    is_active: bool

@router.post("/toggle-status")
def toggle_user_status(
    data: ToggleStatusRequest,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.id == data.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.is_active = data.is_active
        db.commit()
        
        action_str = "ACTIVATED" if data.is_active else "DEACTIVATED"
        log_action(db, current_user.id, "TOGGLE_USER_STATUS", f"Admin {action_str} user {user.email} (ID {user.id})")
        return {"status": "success", "message": f"User status successfully updated to {action_str}"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- Password Recovery & Admin Promotion & Deletion ---

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == data.email).first()
        if not user:
            # Silent fallback to prevent email enumeration
            return {"status": "success", "message": "If the account exists, an OTP has been sent."}
        
        otp_code = f"{random.randint(100000, 999999)}"
        user.otp = otp_code
        db.flush()
        
        send_otp_email(user.email, otp_code)
        db.commit()
        
        log_action(db, user.id, "FORGOT_PASSWORD_REQUEST", f"Password recovery OTP sent to {user.email}")
        return {"status": "success", "message": "Verification OTP sent to email."}
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/forgot-password-verify", response_model=Token)
def forgot_password_verify(data: ForgotPasswordVerifyRequest, db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == data.email).first()
        if not user or user.otp != data.otp:
            raise HTTPException(status_code=400, detail="Invalid email or verification OTP")
        
        user.is_verified = True
        user.otp = None
        db.commit()
        
        log_action(db, user.id, "FORGOT_PASSWORD_LOGIN", f"User logged in via OTP password-less recovery")
        
        access_token = create_access_token(data={"sub": user.email, "role": user.role})
        refresh_token = create_refresh_token(data={"sub": user.email})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": user.role,
            "is_verified": True
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/request-admin")
def request_admin(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        if current_user.role == "admin":
            raise HTTPException(status_code=400, detail="User is already an admin")
        if current_user.base_role == "patient" or current_user.role == "patient":
            raise HTTPException(status_code=403, detail="Patients are not allowed to request admin permissions")
        
        current_user.admin_requested = True
        
        # Notify admins about the request
        admins = db.query(models.User).filter(models.User.role == "admin").all()
        for admin in admins:
            notif = models.Notification(
                user_id=admin.id,
                message=f"User {current_user.email} has requested an Admin Role Promotion.",
                notification_type="admin_promotion_request",
                is_read=False
            )
            db.add(notif)
            
        db.commit()
        
        log_action(db, current_user.id, "REQUEST_ADMIN_ROLE", f"User {current_user.email} requested admin promotion")
        return {"status": "success", "message": "Admin promotion request submitted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/approve-admin/{user_id}")
def approve_admin(
    user_id: int,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    if current_user.email != "sricharanpranav1@gmail.com":
        raise HTTPException(status_code=403, detail="Forbidden. Only the system superadmin can approve admin promotions.")
    
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Just-in-time repair for target user
        is_doctor = db.query(models.Doctor).filter(models.Doctor.user_id == user.id).first() is not None
        if is_doctor and user.base_role == "patient":
            user.base_role = "doctor"
            db.commit()
            
        if user.base_role == "patient" or user.role == "patient":
            raise HTTPException(status_code=400, detail="Patients cannot be promoted to admin")
        
        user.has_admin_permission = True
        user.role = "admin"
        user.admin_requested = False
        
        # Notify the user about the approval
        notif = models.Notification(
            user_id=user.id,
            message="Your Admin Role Promotion request has been approved. Your role has been updated successfully.",
            notification_type="admin_promotion_approved",
            is_read=False
        )
        db.add(notif)
        
        db.commit()
        
        log_action(db, current_user.id, "APPROVE_ADMIN_PROMOTION", f"Superadmin promoted user {user.email} to Admin")
        return {"status": "success", "message": f"User {user.email} successfully promoted to Admin."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/reject-admin/{user_id}")
def reject_admin(
    user_id: int,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    if current_user.email != "sricharanpranav1@gmail.com":
        raise HTTPException(status_code=403, detail="Forbidden. Only the system superadmin can manage admin promotions.")
    
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.admin_requested = False
        
        # Notify the user about the rejection
        notif = models.Notification(
            user_id=user.id,
            message="Your Admin Role Promotion request has been rejected. Please contact the administrator for more information.",
            notification_type="admin_promotion_rejected",
            is_read=False
        )
        db.add(notif)
        
        db.commit()
        
        log_action(db, current_user.id, "REJECT_ADMIN_PROMOTION", f"Superadmin rejected admin request for user {user.email}")
        return {"status": "success", "message": f"Admin request for user {user.email} rejected."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: models.User = Depends(require_role(["admin"])),
    db: Session = Depends(get_db)
):
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own admin account")
        
        # Delete related PatientProfile
        db.query(models.PatientProfile).filter(models.PatientProfile.user_id == user_id).delete(synchronize_session=False)
        
        # Find doctor profile if any
        doc = db.query(models.Doctor).filter(models.Doctor.user_id == user_id).first()
        if doc:
            db.query(models.Appointment).filter(models.Appointment.doctor_id == doc.id).delete(synchronize_session=False)
            db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doc.id).delete(synchronize_session=False)
            db.delete(doc)
            
        db.query(models.Appointment).filter(models.Appointment.patient_id == user_id).delete(synchronize_session=False)
        db.query(models.SymptomLog).filter(models.SymptomLog.user_id == user_id).delete(synchronize_session=False)
        db.query(models.MedicalRecord).filter(models.MedicalRecord.user_id == user_id).delete(synchronize_session=False)
        
        convs = db.query(models.Conversation).filter(models.Conversation.user_id == user_id).all()
        for conv in convs:
            db.query(models.Message).filter(models.Message.conversation_id == conv.id).delete(synchronize_session=False)
            db.delete(conv)
            
        db.query(models.EmergencyAlert).filter(models.EmergencyAlert.patient_id == user_id).delete(synchronize_session=False)
        db.query(models.Complaint).filter(models.Complaint.user_id == user_id).delete(synchronize_session=False)
        db.query(models.PatientMetric).filter(models.PatientMetric.user_id == user_id).delete(synchronize_session=False)
        db.query(models.AuditLog).filter(models.AuditLog.user_id == user_id).delete(synchronize_session=False)
        
        db.delete(user)
        db.commit()
        
        log_action(db, current_user.id, "DELETE_USER", f"Admin deleted user {user.email} (ID {user_id}) and all clinical history")
        return {"status": "success", "message": f"User {user.email} and all history deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch-role")
def switch_role(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.has_admin_permission:
        raise HTTPException(status_code=403, detail="You do not have admin permissions.")
    
    if current_user.base_role == "patient" or current_user.role == "patient":
        raise HTTPException(status_code=403, detail="Patients are not allowed to switch roles to admin")
    
    if current_user.role == "admin":
        # Switch back to base role
        current_user.role = current_user.base_role
    else:
        # Switch to admin mode
        current_user.role = "admin"
        
    db.commit()
    log_action(db, current_user.id, "SWITCH_ROLE", f"User switched active role to {current_user.role}")
    return {
        "status": "success",
        "role": current_user.role,
        "doctor_profile_id": current_user.doctor_profile_id,
        "message": f"Successfully switched to {current_user.role} mode."
    }
