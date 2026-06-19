import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="patient", nullable=False) # patient, doctor, admin, caregiver
    is_active = Column(Boolean, default=True, nullable=False)
    otp = Column(String, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    admin_requested = Column(Boolean, default=False, nullable=False)
    has_admin_permission = Column(Boolean, default=False, nullable=False)
    base_role = Column(String, default="patient", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    profile = relationship("PatientProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    symptom_logs = relationship("SymptomLog", back_populates="user", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    medical_records = relationship("MedicalRecord", back_populates="user", cascade="all, delete-orphan")
    metrics = relationship("PatientMetric", back_populates="user", cascade="all, delete-orphan")
    doctor_profile = relationship("Doctor", back_populates="user", uselist=False, cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="patient", foreign_keys="[Feedback.patient_id]", cascade="all, delete-orphan")
    color_palettes = relationship("UserColorPalette", back_populates="user", cascade="all, delete-orphan")

    @property
    def doctor_profile_id(self):
        return self.doctor_profile.id if self.doctor_profile else None

class PatientProfile(Base):
    __tablename__ = "patient_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String, nullable=False)
    date_of_birth = Column(String, nullable=True) # YYYY-MM-DD
    gender = Column(String, nullable=True)
    height = Column(Float, nullable=True) # in cm
    weight = Column(Float, nullable=True) # in kg
    allergies = Column(Text, nullable=True)
    existing_conditions = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    profile_picture = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="profile")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False) # user or assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

class SymptomLog(Base):
    __tablename__ = "symptom_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symptoms = Column(Text, nullable=False)
    severity = Column(String, nullable=False) # mild, moderate, severe
    duration = Column(String, nullable=False) # e.g. "3 days"
    risk_category = Column(String, nullable=False) # Emergency, Urgent, Routine, Self-Care
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="symptom_logs")

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String, nullable=False)
    specialization = Column(String, nullable=False)
    location = Column(String, nullable=False)
    experience_years = Column(Integer, nullable=False)
    available = Column(Boolean, default=True, nullable=False)
    contact = Column(String, nullable=False)
    address = Column(Text, nullable=True)
    profile_picture = Column(String, nullable=True)
    license_document_path = Column(String, nullable=True)
    license_number = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    appointments = relationship("Appointment", back_populates="doctor", cascade="all, delete-orphan")
    verification = relationship("DoctorVerification", back_populates="doctor", uselist=False, cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="doctor", foreign_keys="[Feedback.doctor_id]", cascade="all, delete-orphan")

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    date = Column(String, nullable=False) # YYYY-MM-DD
    time = Column(String, nullable=False) # HH:MM
    status = Column(String, default="booked", nullable=False) # booked, cancelled, completed
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    patient = relationship("User", back_populates="appointments")
    doctor = relationship("Doctor", back_populates="appointments")
    feedback = relationship("Feedback", back_populates="appointment", uselist=False, cascade="all, delete-orphan")

class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    fraud_status = Column(String, default="VERIFIED (Authentic)", nullable=False)

    # Relationships
    user = relationship("User", back_populates="medical_records")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True) # Can be null if action is system-level or unauthenticated
    action = Column(String, nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class PatientMetric(Base):
    __tablename__ = "patient_metrics"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    metric_type = Column(String, nullable=False) # heart_rate, sleep, steps
    value = Column(String, nullable=False)
    recorded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="metrics")

class DoctorVerification(Base):
    __tablename__ = "doctor_verifications"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    status = Column(String, default="pending", nullable=False) # pending, verified, rejected
    submitted_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    doctor = relationship("Doctor", back_populates="verification")

class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_name = Column(String, nullable=False)
    patient_address = Column(Text, nullable=True)
    status = Column(String, default="active", nullable=False) # active, resolved
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_email = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, default="pending", nullable=False) # pending, resolved
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class PrivateConversation(Base):
    __tablename__ = "private_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("PrivateMessage", back_populates="conversation", cascade="all, delete-orphan")

class PrivateMessage(Base):
    __tablename__ = "private_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("private_conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    attachment_path = Column(String, nullable=True)
    attachment_name = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship("PrivateConversation", back_populates="messages")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False) # chat_message, complaint_submitted, complaint_resolved, general
    related_id = Column(Integer, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationship
    user = relationship("User")


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, unique=True, index=True, nullable=False)
    appointment_id = Column(Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True)
    chat_id = Column(Integer, ForeignKey("private_conversations.id", ondelete="SET NULL"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="INITIATED", nullable=False) # INITIATED, RINGING, ACCEPTED, ONGOING, COMPLETED, DECLINED, MISSED
    initiated_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    metadata_json = Column(Text, default="{}", nullable=True)
    audit_trail = Column(Text, default="[]", nullable=True)


class CallParticipants(Base):
    __tablename__ = "call_participants"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("call_records.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False) # doctor, patient
    joined_at = Column(DateTime, nullable=True)
    left_at = Column(DateTime, nullable=True)
    reconnect_count = Column(Integer, default=0, nullable=False)


class VideoCallAuditLog(Base):
    __tablename__ = "video_call_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("call_records.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    ip_address = Column(String, nullable=False)
    device_info = Column(String, nullable=False)

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), unique=True, nullable=False)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)

    rating_overall = Column(Integer, nullable=False) # 1-5 stars
    rating_doctor = Column(Integer, nullable=False) # 1-5 stars
    comments = Column(Text, nullable=True)

    # Optional category ratings (1-5 stars)
    rating_communication = Column(Integer, nullable=True)
    rating_professionalism = Column(Integer, nullable=True)
    rating_wait_time = Column(Integer, nullable=True)
    rating_satisfaction = Column(Integer, nullable=True)

    is_approved = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)

    # Relationships
    appointment = relationship("Appointment", back_populates="feedback")
    patient = relationship("User", back_populates="feedbacks", foreign_keys=[patient_id])
    doctor = relationship("Doctor", back_populates="feedbacks", foreign_keys=[doctor_id])


class UserColorPalette(Base):
    __tablename__ = "user_color_palettes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    primary_color = Column(String(7), nullable=False)
    secondary_color = Column(String(7), nullable=False)
    background_color = Column(String(7), nullable=False)
    accent_color = Column(String(7), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="color_palettes")
