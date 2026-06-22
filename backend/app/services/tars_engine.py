# tars_engine.py
# Centralized core execution engine for TARS assistant (intent classification, LLM calls, RBAC, side-effects).

import os
import re
import json
import logging
from app.timezone_helper import datetime
from typing import Optional, Dict, Any, List
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from app import models
from app.config import SYSTEM_CAPABILITIES
from app.routes.symptoms import scan_for_emergency
from app.routes.appointments import adjust_timestamps_generic

logger = logging.getLogger(__name__)

OFFLINE_TRANSLATIONS = {
    "en": {
        "emergency": "EMERGENCY WARNING: Severe symptoms detected. Please call 108 or head to the nearest emergency department immediately.",
        "disclaimer": "This is AI-generated information. Please consult a real doctor.",
        "dashboard": "Opening dashboard.",
        "records": "Opening records.",
        "settings": "Opening settings.",
        "chat": "Opening chat.",
        "appointments": "Opening doctors directory.",
        "appointments_spec": "Opening doctors directory for {spec}.",
        "sos": "Triggering SOS.",
        "logout": "Logging out.",
        "hello": "Hello! I am TARS. How can I help you today?"
    },
    "hi": {
        "emergency": "आपातकालीन चेतावनी: गंभीर लक्षण पाए गए हैं। कृपया तुरंत 108 पर कॉल करें या निकटतम आपातकालीन विभाग में जाएं।",
        "disclaimer": "यह एआई-जनरेटेड जानकारी है। कृपया किसी वास्तविक डॉक्टर से सलाह लें।",
        "dashboard": "डैशबोर्ड खोला जा रहा है।",
        "records": "रिकॉर्ड्स खोले जा रहे हैं।",
        "settings": "सेटिंग्स खोली जा रही हैं।",
        "chat": "चैट खोली जा रही है।",
        "appointments": "डॉक्टरों की निर्देशिका खोली जा रही है।",
        "appointments_spec": "{spec} के लिए डॉक्टरों की निर्देशिका खोली जा रही है।",
        "sos": "एसओएस सक्रिय किया जा रहा है।",
        "logout": "लॉगआउट किया जा रहा है।",
        "hello": "नमस्ते! मैं TARS हूँ। आज मैं आपकी क्या सहायता कर सकता हूँ?"
    },
    "te": {
        "emergency": "అత్యవసర హెచ్చరిక: తీవ్రమైన లక్షణాలు గుర్తించబడ్డాయి. దయచేసి వెంటనే 108 కి కాల్ చేయండి లేదా సమీప అత్యవసర విభాగానికి వెళ్ళండి.",
        "disclaimer": "ఇది AI-ఉత్పత్తి చేసిన సమాచారం. దయచేసి నిజమైన వైద్యుడిని సంప్రదించండి.",
        "dashboard": "డాష్‌బోర్డ్ తెరవబడుతోంది.",
        "records": "రికార్డులు తెరవబడుతున్నాయి.",
        "settings": "సెట్టింగ్‌లు తెరవబడుతున్నాయి.",
        "chat": "చాట్ తెరవబడుతోంది.",
        "appointments": "వైద్యుల డైరెక్టరీ తెరవబడుతోంది.",
        "appointments_spec": "{spec} కొరకు వైద్యుల డైరెక్టరీ తెరవబడుతోంది.",
        "sos": "SOS పంపబడుతోంది.",
        "logout": "లాగ్అవుట్ చేయబడుతోంది.",
        "hello": "నమస్తే! నేను TARS. ఈ రోజు నేను మీకు ఎలా సహాయం చేయగలను?"
    }
}

async def execute_tars_intent(
    message: str,
    current_user: models.User,
    db: Session,
    gemini_key: str = "",
    groq_key: str = "",
    hf_key: str = "",
    language: str = ""
) -> Dict[str, Any]:
    """
    Executes a clinical TARS intent command:
    - Runs emergency scans.
    - Saves user messages to the DB history.
    - Compiles user context (appointments, records, doctor directory).
    - Queries LLM models (Gemini Flash, Groq Llama, HF) with fallbacks.
    - Enforces RBAC permissions.
    - Triggers database side-effects (e.g. issuing/fetching prescriptions).
    - Returns structured payload.
    """
    current_msg = message.strip()
    pref_lang = language or "en"
    lang = pref_lang if pref_lang in OFFLINE_TRANSLATIONS else "en"
    disclaimer = OFFLINE_TRANSLATIONS[lang]["disclaimer"]

    # 1. Scan for emergency
    if scan_for_emergency(current_msg):
        reply = OFFLINE_TRANSLATIONS[lang]["emergency"]
        return {
            "message": reply,
            "action": None,
            "disclaimer": disclaimer,
            "reply": reply
        }

    # 2. Find or create a dedicated global assistant conversation thread
    conv = db.query(models.Conversation).filter(
        models.Conversation.user_id == current_user.id,
        models.Conversation.title == "HealthAI Global Assistant"
    ).first()

    if not conv:
        conv = models.Conversation(
            user_id=current_user.id,
            title="HealthAI Global Assistant"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Save user message
    user_msg = models.Message(
        conversation_id=conv.id,
        role="user",
        content=current_msg
    )
    db.add(user_msg)
    db.commit()

    # Load history (last 8 messages)
    history_msgs = db.query(models.Message).filter(
        models.Message.conversation_id == conv.id
    ).order_by(models.Message.timestamp.asc()).all()

    # Fetch current date and time dynamically
    today_date = datetime.date.today()
    today_str = today_date.strftime("%Y-%m-%d")
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Load active/verified doctors directory dynamically
    doctors_query = db.query(models.Doctor).all()
    doctors_list_str = []
    for doc in doctors_query:
        # Get approved leaves
        leaves = db.query(models.LeaveRequest).filter(
            models.LeaveRequest.doctor_id == doc.id,
            models.LeaveRequest.status == "approved"
        ).all()
        leaves_str = ", ".join([f"{l.start_date} to {l.end_date}" for l in leaves]) if leaves else "None"
        
        # Get booked slots
        booked_appts = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == doc.id,
            models.Appointment.status == "booked"
        ).all()
        # Adjust timestamps just in case
        for appt in booked_appts:
            try:
                db.expunge(appt)
            except Exception:
                pass
        adjust_timestamps_generic(booked_appts)
        # Filter for booked slots on or after today
        booked_appts = [a for a in booked_appts if a.date >= today_str]
        booked_appts.sort(key=lambda x: (x.date, x.time))
        booked_str = ", ".join([f"{a.date} at {a.time}" for a in booked_appts]) if booked_appts else "None"
        
        avail_status = "Available" if doc.available else "Unavailable"
        
        doctors_list_str.append(
            f"- {doc.name} ({doc.specialization}, ID {doc.id}) | "
            f"Status: {avail_status} | "
            f"Booked Slots: [{booked_str}] | "
            f"Approved Leaves: [{leaves_str}]"
        )
    doctors_directory = "\n".join(doctors_list_str)

    user_context = (
        f"CURRENT DATE AND TIME: {current_time_str}\n"
        f"CURRENT USER CONTEXT:\n"
        f"- Logged-in User Email: {current_user.email}\n"
        f"- Role: {current_user.role}\n"
        f"- User's Preferred Language/Locale: {pref_lang}\n"
    )

    # Fetch and inject user's medical records
    if current_user.role == "patient":
        medical_records = db.query(models.MedicalRecord).filter(
            models.MedicalRecord.user_id == current_user.id
        ).order_by(models.MedicalRecord.uploaded_at.desc()).all()
        
        records_list = []
        for rec in medical_records:
            records_list.append(f"- Record: {rec.file_name} (Type: {rec.file_type}, ID: {rec.id}, Status: {rec.fraud_status})")
        
        if records_list:
            user_context += "YOUR UPLOADED MEDICAL RECORDS & PRESCRIPTIONS:\n" + "\n".join(records_list) + "\n"
        else:
            user_context += "YOUR UPLOADED MEDICAL RECORDS & PRESCRIPTIONS: You have no uploaded medical records or prescriptions.\n"

        # Fetch patient upcoming appointments
        from sqlalchemy.orm import joinedload
        patient_appts = db.query(models.Appointment).options(
            joinedload(models.Appointment.doctor)
        ).filter(
            models.Appointment.patient_id == current_user.id,
            models.Appointment.status == "booked"
        ).all()
        
        # Expunge to avoid thread binding issues when modifying date/time formats
        for appt in patient_appts:
            try:
                db.expunge(appt)
            except Exception:
                pass
                
        adjust_timestamps_generic(patient_appts)
        patient_appts = [a for a in patient_appts if a.date >= today_str]
        patient_appts.sort(key=lambda x: (x.date, x.time))
    
        appts_list = []
        for appt in patient_appts:
            doc_name = appt.doctor.name if appt.doctor else "Unknown Doctor"
            doc_spec = appt.doctor.specialization if appt.doctor else "Specialist"
            appts_list.append(f"- Appointment with {doc_name} ({doc_spec}) on {appt.date} at {appt.time}")
    
        if appts_list:
            user_context += "YOUR UPCOMING APPOINTMENTS:\n" + "\n".join(appts_list) + "\n"
        else:
            user_context += "YOUR UPCOMING APPOINTMENTS: You have no upcoming appointments scheduled.\n"
        
    elif current_user.role == "doctor":
        doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if not doctor:
            doctor = db.query(models.Doctor).filter(models.Doctor.contact == current_user.email).first()
    
        if doctor:
            from sqlalchemy.orm import joinedload
            doctor_appts = db.query(models.Appointment).options(
                joinedload(models.Appointment.doctor)
            ).filter(
                models.Appointment.doctor_id == doctor.id,
                models.Appointment.status == "booked"
            ).all()
            
            for appt in doctor_appts:
                try:
                    db.expunge(appt)
                except Exception:
                    pass
                    
            adjust_timestamps_generic(doctor_appts)
            doctor_appts = [a for a in doctor_appts if a.date >= today_str]
            doctor_appts.sort(key=lambda x: (x.date, x.time))
        
            consults_list = []
            for appt in doctor_appts:
                p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == appt.patient_id).first()
                p_name = p_profile.name if p_profile else "Unknown Patient"
                consults_list.append(f"- Consultation with patient {p_name} on {appt.date} at {appt.time}")
        
            if consults_list:
                user_context += "YOUR UPCOMING CONSULTATIONS:\n" + "\n".join(consults_list) + "\n"
            else:
                user_context += "YOUR UPCOMING CONSULTATIONS: You have no upcoming consultations scheduled.\n"

            patient_ids = list(set(appt.patient_id for appt in doctor_appts))
            if patient_ids:
                patient_records = db.query(models.MedicalRecord).filter(
                    models.MedicalRecord.user_id.in_(patient_ids)
                ).all()
                doc_records_list = []
                for rec in patient_records:
                    p_profile = db.query(models.PatientProfile).filter(models.PatientProfile.user_id == rec.user_id).first()
                    p_name = p_profile.name if p_profile else "Unknown Patient"
                    doc_records_list.append(f"- Record for patient {p_name} (user_id: {rec.user_id}): {rec.file_name} (Type: {rec.file_type}, ID: {rec.id})")
                if doc_records_list:
                    user_context += "PATIENT MEDICAL RECORDS AVAILABLE TO YOU:\n" + "\n".join(doc_records_list) + "\n"
        else:
            user_context += "YOUR UPCOMING CONSULTATIONS: No doctor profile found.\n"

    system_instructions = (
        "You are TARS, the multilingual voice assistant for a medical web application called HealthAI.\n"
        "Your job is to understand user commands, navigate pages, and trigger allowed actions based on the user's role.\n"
        "Languages you support: English, Hindi, Telugu, Hinglish, Tinglish.\n"
        "Detect the user's input language and writing style (e.g. English, Hindi script, Telugu script, Hinglish, Tinglish) "
        "and respond naturally in the EXACT SAME language, writing script, and style.\n"
        "\n"
        "Rules:\n"
        "1. Act as a voice assistant, not a chatbot. Keep responses short and natural (maximum 2 sentences, 40 words max).\n"
        "2. Never perform actions outside the user's role. If the requested action is not allowed under their role, politely deny it in the 'message' field and return empty action.\n"
        "3. You must classify user intent and return a JSON object with 'intent', 'action', 'parameters', 'message', and 'confidence'.\n"
        "4. Clinic hours are strictly between 08:00 and 20:00. If the user requests an appointment time outside this window (e.g., at 10pm / 22:00), you must politely deny the request in the 'message' field and set action to empty string \"\" (do NOT return createAppointment).\n"
        "5. For greetings, symptom checking, or health questions, do NOT execute any action (set the 'action' field to empty string \"\"), and provide a supportive reply or medical advice in the 'message' field.\n"
        "6. If the user wants to book a visit or find a doctor, and their previous messages or current query relate to a specific organ or condition (like heart/cardiology, skin/dermatology, children/pediatrics, brain/neurology, or general symptoms), specify the appropriate specialization (e.g. 'Cardiology', 'Dermatology', 'Pediatrics', 'Neurology', 'General Medicine') in the 'specialization' parameter of the action (under action: openPage / page_name: appointments).\n"
        "7. If the user's request is incomplete, ambiguous, or lacks required details to execute an action (for example, setting an alarm/reminder without a specified time/purpose, or booking an appointment without a doctor/date/time), you must ask for clarification in the 'message' field and set the 'action' field to an empty string \"\". Do not attempt to guess or execute with default/placeholder parameters unless the user explicitly confirms them.\n"
        f"8. The user's preferred language/locale is '{pref_lang}'. You MUST write your response message in this language/locale.\n"
        "9. Crucial Booking Validation: When proposing or scheduling an appointment, you MUST check the doctor's 'Status', 'Booked Slots', and 'Approved Leaves' in the 'List of available doctors for bookings'. You MUST NOT suggest or schedule any slot if the doctor is 'Unavailable', or if the requested date/time conflicts with their 'Booked Slots' or falls within their 'Approved Leaves' dates. Also, you MUST NOT suggest or schedule any slot that is less than 2 days in advance from the current date and time. If a conflict or violation of these rules occurs, you MUST politely explain the issue and suggest alternative dates/times that are valid.\n"
        "\n"
        "Allowed Action Router Actions:\n"
        "- openPage(page_name, specialization): Navigate the application. Allowed page_name: 'dashboard', 'records', 'chat', 'settings', 'appointments'. Provide 'specialization' parameter if booking a visit related to specific health concerns.\n"
        "- createAppointment(doctor_id, date, time): Schedule a consultation visit.\n"
        "- fetchPrescription(patient_name): Retrieve prescriptions.\n"
        "- updatePatient(latitude, longitude, address): Update patient address/GPS coordinates.\n"
        "- triggerSOS(): Escalate emergency alerts.\n"
        "- logout(): Sign out from the session.\n"
        "- setReminder(medicine_name, dosage, time, days, method): Schedule medication reminders.\n"
        "- createPrescription(patient_name, diagnosis, medicines, instructions): Issue clinical prescription (DOCTOR only).\n"
        "\n"
        "Roles & Permissions:\n"
        "PATIENT: can openPage, createAppointment, fetchPrescription (self), updatePatient, triggerSOS, logout, setReminder.\n"
        "DOCTOR: can openPage, fetchPrescription (other patients), triggerSOS, logout, setReminder, createPrescription.\n"
        "ADMIN: can openPage, fetchPrescription, triggerSOS, logout, setReminder.\n"
        "\n"
        "List of available doctors for bookings:\n"
        f"{doctors_directory}\n"
        "\n"
        f"{user_context}"
    )

    messages_payload = [
        {
            "role": "system",
            "content": system_instructions
        }
    ]

    for h_msg in history_msgs[-8:]:
        messages_payload.append({"role": h_msg.role, "content": h_msg.content})

    gemini_api_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
    groq_api_key = groq_key or os.getenv("GROQ_API_KEY", "")
    hf_api_key = hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))

    has_gemini = gemini_api_key and not gemini_api_key.startswith("your_gemini_api_key")
    has_groq = groq_api_key and not groq_api_key.startswith("your_groq_api_key")
    has_hf = hf_api_key and not hf_api_key.startswith("your_hf_api_key")

    reply = ""

    # 1. Primary Model: Gemini 2.5 Flash
    if has_gemini:
        try:
            gemini_contents = []
            for msg in history_msgs[-8:]:
                role = "model" if msg.role == "assistant" else "user"
                content_clean = msg.content
                if msg.role == "assistant" and "[" in content_clean:
                    content_clean = re.sub(r'\[ACTION:[\s\S]*?\]', '', content_clean).strip()
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": content_clean}]
                })
            
            gemini_contents.append({
                "role": "user",
                "parts": [{"text": current_msg}]
            })
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": gemini_contents,
                        "systemInstruction": {
                            "parts": [{"text": system_instructions}]
                        },
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": {
                                "type": "OBJECT",
                                "properties": {
                                    "intent": {"type": "STRING"},
                                    "action": {"type": "STRING"},
                                    "parameters": {
                                        "type": "OBJECT",
                                        "properties": {
                                            "page_name": {"type": "STRING"},
                                            "specialization": {"type": "STRING"},
                                            "doctor_id": {"type": "STRING"},
                                            "date": {"type": "STRING"},
                                            "time": {"type": "STRING"},
                                            "patient_name": {"type": "STRING"},
                                            "latitude": {"type": "NUMBER"},
                                            "longitude": {"type": "NUMBER"},
                                            "address": {"type": "STRING"},
                                            "medicine_name": {"type": "STRING"},
                                            "dosage": {"type": "STRING"},
                                            "days": {"type": "STRING"},
                                            "method": {"type": "STRING"}
                                        }
                                    },
                                    "message": {"type": "STRING"},
                                    "confidence": {"type": "NUMBER"}
                                },
                                "required": ["intent", "action", "parameters", "message", "confidence"]
                            }
                        }
                    },
                    timeout=8.0
                )
                if response.status_code == 200:
                    res_obj = response.json()
                    parts = res_obj.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])
                    if parts:
                        reply = parts[0].get("text", "").strip()
                else:
                    logger.error(f"Gemini API returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Gemini 2.5 Flash error: {e}")

    # 2. Backup Model 1: Groq
    if not reply and has_groq:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": messages_payload,
                        "temperature": 0.2,
                        "stream": False
                    },
                    timeout=8.0
                )
                if response.status_code == 200:
                    res_obj = response.json()
                    reply = res_obj["choices"][0]["message"].get("content", "").strip()
                else:
                    logger.error(f"Groq API status: {response.status_code}")
        except Exception as e:
            logger.error(f"Groq error: {e}")

    # 3. Backup Model 2: Hugging Face
    if not reply and has_hf:
        try:
            async with httpx.AsyncClient() as client:
                prompt = ""
                for msg in messages_payload:
                    role_tag = "<|system|>" if msg["role"] == "system" else "<|user|>" if msg["role"] == "user" else "<|assistant|>"
                    prompt += f"{role_tag}\n{msg['content']}\n"
                prompt += "<|assistant|>\n"
                response = await client.post(
                    "https://api-inference.huggingface.co/models/meta-llama/Llama-3.2-3B-Instruct",
                    headers={
                        "Authorization": f"Bearer {hf_api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "inputs": prompt,
                        "parameters": {"max_new_tokens": 250, "temperature": 0.2}
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    res_json = response.json()
                    if isinstance(res_json, list) and len(res_json) > 0:
                        generated = res_json[0].get("generated_text", "")
                        if "<|assistant|>" in generated:
                            reply = generated.split("<|assistant|>")[-1].strip()
                        else:
                            reply = generated.replace(prompt, "").strip()
        except Exception as e:
            logger.error(f"Hugging Face error: {e}")

    intent = ""
    action_type = None
    action_params = {}
    message = ""
    confidence = 0.0

    if reply:
        clean_reply = reply.strip()
        if clean_reply.startswith("```"):
            lines = clean_reply.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_reply = "\n".join(lines).strip()
        
        try:
            start_idx = clean_reply.find('{')
            end_idx = clean_reply.rfind('}')
            if start_idx != -1 and end_idx != -1:
                json_str = clean_reply[start_idx:end_idx+1]
                parsed_json = json.loads(json_str)
                intent = parsed_json.get("intent", "")
                action_type = parsed_json.get("action", "")
                action_params = parsed_json.get("parameters", {})
                message = parsed_json.get("message", "")
                confidence = parsed_json.get("confidence", 0.0)
            else:
                # Try parsing key-value pairs via regex if the LLM output is not JSON
                intent_match = re.search(r'(?i)intent:\s*(.*)', clean_reply)
                action_match = re.search(r'(?i)action:\s*(.*)', clean_reply)
                message_match = re.search(r'(?i)message:\s*([\s\S]*?)(?=\n\s*(?:intent|action|parameters|confidence|disclaimer):|$)', clean_reply)
                confidence_match = re.search(r'(?i)confidence:\s*([\d.]+)', clean_reply)
                
                if message_match:
                    message = message_match.group(1).strip()
                    intent = intent_match.group(1).strip() if intent_match else ""
                    action_type = action_match.group(1).strip() if action_match else ""
                    try:
                        confidence = float(confidence_match.group(1).strip()) if confidence_match else 0.0
                    except Exception:
                        confidence = 0.0
                else:
                    message = reply
        except Exception as pe:
            logger.error(f"JSON parsing error: {pe}. Using raw reply.")
            message = reply

    # 4. Offline Fallback if no LLM response could be fetched
    if not message:
        msg_lower = current_msg.lower()
        is_schedule_query = any(k in msg_lower for k in ["show", "read", "view", "what", "my", "list", "check", "శెడ్యూల్", "అపాయింట్మెంట్", "షెడ్యూల్", "अपॉइंटमेंट", "शेड्यूल"]) and any(k in msg_lower for k in ["appointment", "appointments", "consultation", "consultations", "schedule", "visit", "visits", "meeting", "meetings", "record", "records"])
        is_booking_intent = any(k in msg_lower for k in ["book", "schedule", "appointment", "अपॉइंटमेंट", "అపాయింట్మెంట్"])
        
        lang = pref_lang if pref_lang in OFFLINE_TRANSLATIONS else "en"
        trans = OFFLINE_TRANSLATIONS[lang]
        
        if is_schedule_query:
            intent = "view_schedule"
            action_type = "openPage"
            action_params = {"page_name": "dashboard"}
            message = trans["dashboard"]
        elif is_booking_intent:
            intent = "book_appointment"
            action_type = "openPage"
            spec = ""
            if any(k in msg_lower for k in ["heart", "chest", "cardio", "दिल", "గుండె"]):
                spec = "Cardiology"
            elif any(k in msg_lower for k in ["skin", "hair", "dermatology", "त्वचा", "చర్మం"]):
                spec = "Dermatology"
            elif any(k in msg_lower for k in ["brain", "neurology", "दिमाग", "మెదడు"]):
                spec = "Neurology"
            elif any(k in msg_lower for k in ["child", "pediatrics", "बच्चा", "పిల్లలు"]):
                spec = "Pediatrics"
            action_params = {"page_name": "appointments", "specialization": spec}
            if spec:
                message = trans["appointments_spec"].format(spec=spec)
            else:
                message = trans["appointments"]
        elif "record" in msg_lower or "prescription" in msg_lower or "file" in msg_lower or "report" in msg_lower:
            intent = "view_records"
            action_type = "openPage"
            action_params = {"page_name": "records"}
            message = trans["records"]
        elif "setting" in msg_lower or "profile" in msg_lower:
            intent = "view_settings"
            action_type = "openPage"
            action_params = {"page_name": "settings"}
            message = trans["settings"]
        elif "chat" in msg_lower or "message" in msg_lower:
            intent = "view_chat"
            action_type = "openPage"
            action_params = {"page_name": "chat"}
            message = trans["chat"]
        elif "sos" in msg_lower or "emergency" in msg_lower:
            intent = "trigger_sos"
            action_type = "triggerSOS"
            message = trans["sos"]
        elif "logout" in msg_lower or "sign out" in msg_lower:
            intent = "logout"
            action_type = "logout"
            message = trans["logout"]
        else:
            intent = "common_help"
            message = trans["hello"]

    # Structure action payload
    action_payload = None
    if action_type:
        if action_type == 'OPEN_DOCTORS' or action_type == 'find_doctors':
            action_type = 'openPage'
            spec = action_params.get("specialization", "")
            action_params = {"page_name": "appointments", "specialization": spec}
        elif action_type in ['OPEN_PRESCRIPTIONS', 'OPEN_RECORDS', 'view_records']:
            action_type = 'openPage'
            action_params = {"page_name": "records"}
        elif action_type in ['OPEN_DASHBOARD', 'OPEN_WORKSPACE', 'OPEN_ADMIN_PORTAL', 'view_dashboard']:
            action_type = 'openPage'
            action_params = {"page_name": "dashboard"}
        elif action_type in ['OPEN_SETTINGS', 'view_settings']:
            action_type = 'openPage'
            action_params = {"page_name": "settings"}
        elif action_type in ['OPEN_CHAT', 'view_chat']:
            action_type = 'openPage'
            action_params = {"page_name": "chat"}
        elif action_type in ['book_appointment', 'bookAppointment', 'create_appointment', 'createAppointment']:
            action_type = 'createAppointment'
        elif action_type in ['trigger_sos', 'triggerSOS', 'triggerSos']:
            action_type = 'triggerSOS'
        elif action_type in ['logout', 'signout', 'signOut', 'sign_out']:
            action_type = 'logout'
        elif action_type in ['set_reminder', 'setReminder', 'createReminder', 'create_reminder']:
            action_type = 'setReminder'

        action_payload = {
            "type": action_type,
            "parameters": action_params
        }

    # Enforce Role-Based Access Control (RBAC)
    user_role = current_user.role.lower() if current_user.role else "patient"
    role_permissions = SYSTEM_CAPABILITIES.get("roles", {}).get(user_role, {}).get("permissions", [])
    
    if action_payload:
        act_name = action_payload["type"]
        if act_name not in ["logout", "triggerSOS"] and act_name not in role_permissions:
            action_payload = None
            if user_role == "doctor":
                message = "Access Denied: As a doctor, you do not have permission to execute this action."
            elif user_role == "admin":
                message = "Access Denied: As an admin, you do not have permission to execute this action."
            else:
                message = "Access Denied: Under your role, you do not have permission to execute this action."

    # FetchPrescription Side-effect (DB query for prescriptions)
    if action_payload and action_payload["type"] == "fetchPrescription":
        target_user_id = current_user.id
        patient_found_name = current_user.email
        p_name_param = action_params.get("patient_name")
        
        if p_name_param and current_user.role in ["doctor", "admin"]:
            p_profile = db.query(models.PatientProfile).filter(
                models.PatientProfile.name.ilike(f"%{p_name_param}%")
            ).first()
            if p_profile:
                target_user_id = p_profile.user_id
                patient_found_name = p_profile.name
            else:
                target_user_id = None
        
        if target_user_id:
            prescriptions = db.query(models.MedicalRecord).filter(
                models.MedicalRecord.user_id == target_user_id,
                models.MedicalRecord.file_name.ilike("Prescription_%")
            ).all()
            
            if prescriptions:
                action_params["prescriptions"] = [
                    {
                        "id": p.id,
                        "file_name": p.file_name,
                        "file_path": p.file_path,
                        "uploaded_at": p.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
                    }
                    for p in prescriptions
                ]
                presc_list_str = ", ".join([p.file_name for p in prescriptions])
                message = f"Found the following prescriptions for {patient_found_name if p_name_param else 'you'}: {presc_list_str}."
            else:
                message = f"No prescriptions found for {patient_found_name if p_name_param else 'you'}."
                action_params["prescriptions"] = []
        else:
            message = f"Could not find patient profile matching '{p_name_param}'."
            action_params["prescriptions"] = []

    # CreatePrescription Side-effect (doctor only)
    if action_payload and action_payload["type"] == "createPrescription" and user_role == "doctor":
        try:
            params = action_payload.get("parameters", {})
            p_name = params.get("patient_name")
            diagnosis = params.get("diagnosis")
            medicines = params.get("medicines", [])
            instructions = params.get("instructions", "")
            
            p_profile = db.query(models.PatientProfile).filter(
                models.PatientProfile.name.ilike(f"%{p_name}%")
            ).first()
            
            if p_profile:
                recipient_id = p_profile.user_id
                conv_db = db.query(models.PrivateConversation).filter(
                    or_(
                        and_(models.PrivateConversation.user1_id == current_user.id, models.PrivateConversation.user2_id == recipient_id),
                        and_(models.PrivateConversation.user1_id == recipient_id, models.PrivateConversation.user2_id == current_user.id)
                    )
                ).first()
                if not conv_db:
                    conv_db = models.PrivateConversation(
                        user1_id=current_user.id,
                        user2_id=recipient_id
                    )
                    db.add(conv_db)
                    db.commit()
                    db.refresh(conv_db)
                
                from app.routes.chats import create_prescription_internal
                create_prescription_internal(
                    db=db,
                    conversation_id=conv_db.id,
                    current_user=current_user,
                    patient_name=p_profile.name,
                    diagnosis=diagnosis,
                    medicines=medicines,
                    instructions=instructions
                )
                message = f"Prescription issued successfully for {p_profile.name}."
        except Exception as ex:
            logger.error(f"Failed to issue prescription in backend: {ex}")

    # Save final response to the Message log in database
    assistant_msg = models.Message(
        conversation_id=conv.id,
        role="assistant",
        content=f"{message}\n\n[Disclaimer: {disclaimer}]"
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "message": message,
        "action": action_payload,
        "disclaimer": disclaimer,
        "reply": message
    }
