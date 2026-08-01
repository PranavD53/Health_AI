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

def normalize_specialization(spec: str) -> str:
    if not spec:
        return ""
    spec_lower = spec.lower()
    if any(k in spec_lower for k in ["cardio", "heart", "గుండె", "హృదయ", "दिल", "हृदय"]):
        return "Cardiology"
    if any(k in spec_lower for k in ["derm", "skin", "చర్మ", "త్వచ"]):
        return "Dermatology"
    if any(k in spec_lower for k in ["neuro", "brain", "నరాల", "మెదడు", "नसों", "न्यूरो"]):
        return "Neurology"
    if any(k in spec_lower for k in ["pediatr", "child", "పిల్లల", "बाल"]):
        return "Pediatrics"
    if any(k in spec_lower for k in ["general", "medicine", "జనరల్", "सामान्य"]):
        return "General Medicine"
    return spec


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

def detect_user_message_language(message: str, client_language: str) -> str:
    if not message:
        return "en"
    
    # Check native script characters
    if re.search(r'[\u0C00-\u0C7F]', message): # Telugu
        return "te"
    if re.search(r'[\u0900-\u097F]', message): # Hindi
        return "hi"
        
    # Check Hinglish/Tinglish romanized text keywords
    text_lower = message.lower()
    hinglish_keywords = [
        "namaste", "aap", "chahiye", "hai", "kya", "mera", "hu", "ho", "bhai", "shukriya", "dost", "kar", 
        "se", "ko", "par", "ek", "apko", "karo", "karna", "acha", "theek", "aapko", "karke", "sojao", 
        "band", "kholo", "so jao", "utho", "shuru", "chahiye", "chahye", "he", "mujhe", "mujhko", "mera", "meri"
    ]
    tinglish_keywords = [
        "namaskaram", "enti", "ela", "undhi", "avunu", "kadhu", "cheyyandi", "nenu", "miru", "naa", 
        "bhayam", "gurinchi", "vundhi", "vundi", "cheyandi", "meluko", "paduko", "oddu", "kavali", "naaku", 
        "kavaali", "naku", "kavalii"
    ]
    
    # Count occurrences as whole words
    hi_matches = sum(1 for w in hinglish_keywords if f" {w} " in f" {text_lower} ")
    te_matches = sum(1 for w in tinglish_keywords if f" {w} " in f" {text_lower} ")
    
    if hi_matches > 0 or te_matches > 0:
        if hi_matches >= te_matches:
            return "hi"
        else:
            return "te"
            
    # Check for common English words to enforce answering in English if typed in English
    english_words = {
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with", 
        "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", 
        "she", "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up", 
        "out", "if", "about", "who", "get", "which", "go", "me", "your", "can", "tell", "report", "medical",
        "show", "view", "what", "appointment", "doctor", "help", "please", "am", "are", "was", "were",
        "has", "had", "any", "other", "some", "no", "yes", "than", "then", "them", "cancer", "illness",
        "disease", "sick", "pain", "fever", "cough", "throat", "headache", "appointment", "schedule", "book",
        "critical", "using", "tell"
    }
    
    en_matches = sum(1 for w in english_words if f" {w} " in f" {text_lower} ")
    if en_matches > 0:
        return "en"
        
    # Normalize client language (e.g. 'en-US' -> 'en')
    client_lang = "en"
    if client_language:
        client_lang = client_language.split("-")[0].strip().lower()
        
    return client_lang


def extract_clean_message(reply: str) -> Dict[str, Any]:
    intent = "common_help"
    action_type = None
    action_params = {}
    message = ""
    confidence = 0.9
    
    clean_reply = reply.strip()
    
    # Remove markdown code block symbols
    if clean_reply.startswith("```"):
        lines = clean_reply.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_reply = "\n".join(lines).strip()

    # Try parsing as JSON first
    parsed_json = None
    start_idx = clean_reply.find('{')
    end_idx = clean_reply.rfind('}')
    if start_idx != -1 and end_idx != -1:
        json_str = clean_reply[start_idx:end_idx+1]
        try:
            parsed_json = json.loads(json_str)
        except Exception:
            # Try fixing common malformed JSON issues like trailing commas or missing confidence values
            fixed_json_str = re.sub(r'"confidence"\s*:\s*}(?=\s*$)', '"confidence": 0.95}', json_str)
            fixed_json_str = re.sub(r'"confidence"\s*:\s*,\s*}', '"confidence": 0.95}', fixed_json_str)
            fixed_json_str = re.sub(r',\s*}(?=\s*$)', '}', fixed_json_str)
            try:
                parsed_json = json.loads(fixed_json_str)
            except Exception:
                pass

    if parsed_json:
        intent = parsed_json.get("intent", "common_help")
        action_type = parsed_json.get("action", "")
        action_params = parsed_json.get("parameters", {})
        message = parsed_json.get("message", "")
        confidence = parsed_json.get("confidence", 0.9)
    else:
        # Fallback to key-value extraction using regex
        normalized_reply = re.sub(r'(?i)\*\*(intent|action|parameters|message|confidence|disclaimer)\*\*:', r'\1:', clean_reply)
        normalized_reply = re.sub(r'(?i)\*(intent|action|parameters|message|confidence|disclaimer)\*:', r'\1:', normalized_reply)
        
        intent_match = re.search(r'(?i)intent:\s*"?([^"\n]+)"?', normalized_reply)
        action_match = re.search(r'(?i)action:\s*"?([^"\n]+)"?', normalized_reply)
        message_match = re.search(r'(?i)message:\s*"?([\s\S]*?)"?(?=\n\s*(?:intent|action|parameters|confidence|disclaimer):|$)', normalized_reply)
        confidence_match = re.search(r'(?i)confidence:\s*([\d.]+)', normalized_reply)
        
        if message_match:
            message = message_match.group(1).strip()
            intent = intent_match.group(1).strip() if intent_match else "common_help"
            action_type = action_match.group(1).strip() if action_match else ""
            try:
                confidence = float(confidence_match.group(1).strip()) if confidence_match else 0.9
            except Exception:
                confidence = 0.9
        else:
            # If everything else fails, extract the message text from any double-quoted block inside the response
            msg_double_quote_match = re.search(r'"message"\s*:\s*"([^"]+)"', clean_reply)
            if msg_double_quote_match:
                message = msg_double_quote_match.group(1).strip()
            else:
                # Fallback: clean the reply from any JSON brackets, keywords, or labels
                message = clean_reply
                # If there is a JSON block inside, take the text before it
                if "{" in message:
                    parts = message.split("{")
                    before_json = parts[0].replace("JSON Response:", "").replace("json", "").strip()
                    if len(before_json) > 10:
                        message = before_json
                
                # Scrub other labels
                message = re.sub(r'(?i)\b(?:intent|action|parameters|confidence|disclaimer|page_name|specialization)\b.*', '', message)
                message = re.sub(r'[{}\[\]"\'_:-]', ' ', message)
                message = re.sub(r'\s+', ' ', message).strip()
                
        # Extract parameters from non-JSON structured response via regex if needed
        action_params = {}
        param_json_match = re.search(r'(?i)parameters:\s*(\{[\s\S]*?\})', normalized_reply)
        if param_json_match:
            try:
                action_params = json.loads(param_json_match.group(1).strip())
            except Exception:
                pass
        
        if not action_params:
            p_name_match = re.search(r'(?i)(?:page_name|page|pageName):\s*([a-zA-Z0-9_-]+)', normalized_reply)
            spec_match = re.search(r'(?i)(?:specialization|speciality|specialityName|spec):\s*([a-zA-Z0-9_ -]+)', normalized_reply)
            if p_name_match:
                action_params["page_name"] = p_name_match.group(1).strip()
            if spec_match:
                action_params["specialization"] = spec_match.group(1).strip()

    # Double check that we scrub any confidence scores or AI measures from the message field
    if isinstance(message, str):
        message = re.sub(r'(?i)\[\s*confidence\s*:\s*[\d.%/]+\s*\]', '', message)
        message = re.sub(r'(?i)(?:with\s+)?(?:\d+(?:\.\d+)?%|\b0\.\d+|\b1\.0)(?:\s+)?(?:confidence|accuracy)\b', '', message)
        message = re.sub(r'(?i)\bconfidence(?:\s+score)?(?:\s*:\s*|\s+is\s+)[\d.%/]+', '', message)
        message = re.sub(r'(?i)\b(?:intent|classification|llm|ai|model|action)\b(?:\s+is\s+|\s*:\s*)[\w_]+', '', message)
        message = re.sub(r'(?i)\[\s*(?:confidence|score|note|action|intent)[\s\S]*?\]', '', message)
        message = re.sub(r'(?i)\(\s*(?:confidence|score|note|action|intent)[\s\S]*?\)', '', message)
        message = re.sub(r'(?i)\(\s*note\s*:\s*[\s\S]*?\)', '', message)
        message = re.sub(r'(?i)\[\s*note\s*:\s*[\s\S]*?\]', '', message)
        # Strip trailing mismatched brackets or quotes
        message = message.replace("**", "").replace("*", "")
        message = message.strip()
        if message.endswith("]") and "[" not in message:
            message = message[:-1].strip()
        if message.endswith(")") and "(" not in message:
            message = message[:-1].strip()
        if message.endswith('"') and '"' not in message[:-1]:
            message = message[:-1].strip()
        
    return {
        "intent": intent,
        "action": action_type,
        "parameters": action_params,
        "message": message,
        "confidence": confidence
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
    
    # Dynamically detect language from the user's message, bypassing global selection
    detected_lang = detect_user_message_language(current_msg, language)
    pref_lang = detected_lang
    lang = pref_lang if pref_lang in OFFLINE_TRANSLATIONS else "en"
    disclaimer = OFFLINE_TRANSLATIONS[lang]["disclaimer"]

    gemini_api_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
    groq_api_key = groq_key or os.getenv("GROQ_API_KEY", "")
    hf_api_key = hf_key or os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))

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
            insights_part = f", AI Insights: {rec.analysis_insights}" if rec.analysis_insights else ""
            meds_part = f", Suggested Medications: {rec.analysis_medications}" if rec.analysis_medications else ""
            records_list.append(f"- Record: {rec.file_name} (Type: {rec.file_type}, ID: {rec.id}, Status: {rec.fraud_status}{insights_part}{meds_part})")
        
        if records_list:
            user_context += "YOUR UPLOADED MEDICAL RECORDS & PRESCRIPTIONS:\n" + "\n".join(records_list) + "\n"
        else:
            user_context += "YOUR UPLOADED MEDICAL RECORDS & PRESCRIPTIONS: You have no uploaded medical records or prescriptions.\n"

        imaging_records = db.query(models.MedicalImagingDiagnostic).filter(
            models.MedicalImagingDiagnostic.user_id == current_user.id
        ).order_by(models.MedicalImagingDiagnostic.created_at.desc()).all()
        
        imaging_list = []
        for img in imaging_records:
            clean_findings = img.findings.split('[Diagnostic')[0].strip().replace('\n', ' ') if img.findings else "No findings recorded"
            imaging_list.append(f"- Imaging Diagnostic Scan: {img.file_name} (Category: {img.scan_type}, ID: {img.id}, Severity: {img.severity}, Specialist: {img.recommended_specialist}, Findings: {clean_findings})")
        
        if imaging_list:
            user_context += "YOUR IMAGING DIAGNOSTICS HISTORY:\n" + "\n".join(imaging_list) + "\n"
        else:
            user_context += "YOUR IMAGING DIAGNOSTICS HISTORY: You have no imaging diagnostic reports.\n"

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

    # Retrieve clinical guidelines (RAG) for medical safety
    from app.services.rag_engine import retrieve_clinical_guidelines
    guidelines = []
    citations = []
    guideline_ref = "No specific clinical guideline reference available."
    try:
        guidelines = await retrieve_clinical_guidelines(
            db=db,
            query=current_msg,
            hf_key=hf_api_key,
            gemini_key=gemini_api_key
        )
        if guidelines:
            guideline_ref = "\n".join([
                f"- Document: {g.title} | Source Citation: {g.source_citation}\n  Guideline content: {g.content}"
                for g in guidelines
            ])
            citations = [g.source_citation for g in guidelines]
    except Exception as RAG_err:
        logger.error(f"RAG: Retrieval error: {RAG_err}")

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
        "3. You must classify user intent and return a JSON object with 'intent', 'action', 'parameters', 'message', and 'confidence'. The JSON 'confidence' field must always be a valid floating-point number (e.g. 0.95 or 1.0). You must return ONLY the raw JSON object, without any markdown code block formatting (like ```json), without any conversational prefix, suffix, label, or preamble. Do not explain your choices. Your response must be directly parseable as a JSON object. However, you must NEVER mention confidence scores, AI metrics, LLM terms, classification details, or intent/action names within the 'message' field. The 'message' field must remain strictly human-like, conversational, and direct.\n"
        "4. Clinic hours are strictly between 08:00 and 20:00. If the user requests an appointment time outside this window (e.g., at 10pm / 22:00), or if the requested appointment date is less than 2 days in the future (relative to the CURRENT DATE AND TIME provided), you must politely deny the request in the 'message' field (explaining the 2-day advance or clinic hour restriction) and set the 'action' field to an empty string \"\" (do NOT return createAppointment).\n"
        "5. For greetings, symptom checking, or health questions, do NOT execute any action (set the 'action' field to empty string \"\"), and provide a supportive reply or medical advice in the 'message' field. Crucial Medication Rule: If the symptoms represent a mild or low severity condition (like mild fever, minor sore throat, simple cough, mild skin itching), you MUST suggest appropriate, safe over-the-counter (OTC) or mild medicines (such as paracetamol for fever, throat lozenges for sore throat, antihistamines for allergies, or topical calamine/emollients for skin itching) directly inside the message response, while advising them to consult a doctor if symptoms persist.\n"
        "6. If the user wants to book a visit or find a doctor, and their previous messages or current query relate to a specific organ or condition (like heart/cardiology, skin/dermatology, children/pediatrics, brain/neurology, or general symptoms), specify the appropriate specialization (e.g. 'Cardiology', 'Dermatology', 'Pediatrics', 'Neurology', 'General Medicine') in the 'specialization' parameter of the action (under action: openPage / page_name: appointments). Crucial Mapping Rule: If the user asks for a doctor related to their 'problem', 'record', or 'scan' without specifying the name or department, you MUST check their context reports history. If their recent scan recommended a 'dermatologist' or indicates a skin condition, set the specialization parameter to 'Dermatology'; if a heart scan, set to 'Cardiology'; if child/pediatric, set to 'Pediatrics'; if brain/neurology, set to 'Neurology'; otherwise default to 'General Medicine'.\n"
        "7. If the user's request is incomplete, ambiguous, or lacks required details to execute an action (for example, setting an alarm/reminder without a specified time/purpose, or booking an appointment without a doctor/date/time), you must ask for clarification in the 'message' field and set the 'action' field to an empty string \"\". Do not attempt to guess or execute with default/placeholder parameters unless the user explicitly confirms them.\n"
        f"8. The user's message is detected to be in '{pref_lang}' style. You MUST respond in this language/dialect (e.g., reply in Hinglish if they ask in Hinglish, and reply in Tinglish if they ask in Tinglish, matching their script style).\n"
        "9. For actions that perform database modifications or background operations (like 'createAppointment', 'updatePatient', 'setReminder'), the 'message' field should state that you are *attempting* or *proceeding* to perform the action (e.g., 'I will proceed to book that appointment for you...', 'Updating your location now...', 'Setting a medication reminder...'), rather than asserting that the action has already succeeded, as the actual execution runs asynchronously after your response is returned.\n"
        "10. Crucial Booking Validation: When proposing or scheduling an appointment, you MUST check the doctor's 'Status', 'Booked Slots', and 'Approved Leaves' in the 'List of available doctors for bookings'. You MUST NOT suggest or schedule any slot if the doctor is 'Unavailable', or if the requested date/time conflicts with their 'Booked Slots' or falls within their 'Approved Leaves' dates. Also, you MUST NOT suggest or schedule any slot that is less than 2 days in advance from the current date and time. If a conflict or violation of these rules occurs, you MUST politely explain the issue and suggest alternative dates/times that are valid.\n"
        "\n"
        "- openPage(page_name, specialization): Navigate the application. Allowed page_name: 'dashboard', 'records', 'chat', 'settings', 'appointments'. Provide 'specialization' parameter if booking a visit related to specific health concerns.\n"
        "- createAppointment(doctor_id, date, time): Schedule a consultation visit.\n"
        "- fetchPrescription(patient_name): Retrieve prescriptions.\n"
        "- updatePatient(latitude, longitude, address): Update patient address/GPS coordinates.\n"
        "- triggerSOS(): Escalate emergency alerts.\n"
        "- logout(): Sign out from the session.\n"
        "- setReminder(medicine_name, dosage, time, days, method): Schedule medication reminders.\n"
        "- createPrescription(patient_name, diagnosis, medicines, instructions): Issue clinical prescription (DOCTOR only).\n"
        "- openMedicalRecord(record_id, file_path): Open a specific uploaded medical record or prescription PDF/image file from the list. Must supply the record_id and file_path from context.\n"
        "- openImagingDiagnostic(diagnostic_id): Open a specific clinical visual diagnostics report from history. Must supply the diagnostic_id (ID) from history.\n"
        "\n"
        "Roles & Permissions:\n"
        "PATIENT: can openPage, createAppointment, fetchPrescription (self), updatePatient, triggerSOS, logout, setReminder.\n"
        "DOCTOR: can openPage, fetchPrescription (other patients), triggerSOS, logout, setReminder, createPrescription.\n"
        "ADMIN: can openPage, fetchPrescription, triggerSOS, logout, setReminder.\n"
        "\n"
        "List of available doctors for bookings:\n"
        f"{doctors_directory}\n"
        "\n"
        "CLINICAL GUIDELINE REFERENCE MATERIAL:\n"
        "You MUST base your medical advice strictly on the verified clinical reference guidelines below. "
        "Explicitly cite the source citations (e.g. '[Source: Merck Manual]') directly in your response text.\n"
        f"{guideline_ref}\n"
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

    # API keys loaded at start of execute_tars_intent

    has_gemini = gemini_api_key and not gemini_api_key.startswith("your_gemini_api_key")
    has_groq = groq_api_key and not groq_api_key.startswith("your_groq_api_key")
    has_hf = hf_api_key and not hf_api_key.startswith("your_hf_api_key")

    reply = ""

    # 1. Primary Model: Gemini 2.5 Flash
    if has_gemini:
        try:
            gemini_contents = []
            # Exclude the latest user message (which is already appended to history_msgs) to avoid duplication
            for msg in history_msgs[:-1][-7:]:
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
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
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
        parsed_result = extract_clean_message(reply)
        intent = parsed_result["intent"]
        action_type = parsed_result["action"]
        action_params = parsed_result["parameters"]
        message = parsed_result["message"]
        confidence = parsed_result["confidence"]

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
            
            # Context-aware fallback: query patient's diagnostic history if specialization not specified in prompt
            if not spec and current_user.role == "patient":
                latest_scan = db.query(models.MedicalImagingDiagnostic).filter(
                    models.MedicalImagingDiagnostic.user_id == current_user.id
                ).order_by(models.MedicalImagingDiagnostic.created_at.desc()).first()
                if latest_scan and latest_scan.recommended_specialist:
                    spec_map = {
                        "dermatologist": "Dermatology",
                        "dermatology": "Dermatology",
                        "cardiologist": "Cardiology",
                        "cardiology": "Cardiology",
                        "neurologist": "Neurology",
                        "neurology": "Neurology",
                        "pediatrician": "Pediatrics",
                        "pediatrics": "Pediatrics",
                        "general": "General Medicine"
                    }
                    spec = spec_map.get(latest_scan.recommended_specialist.lower().strip(), "")
                    
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
        if action_type in ['open_page', 'openpage', 'openPage', 'OPEN_PAGE']:
            action_type = 'openPage'
            p_name = action_params.get("page_name", "")
            if p_name:
                p_name_lower = p_name.lower().strip()
                if "appoint" in p_name_lower or "doctor" in p_name_lower:
                    action_params["page_name"] = "appointments"
                    spec = normalize_specialization(action_params.get("specialization", ""))
                    if not spec and current_user.role == "patient":
                        latest_scan = db.query(models.MedicalImagingDiagnostic).filter(
                            models.MedicalImagingDiagnostic.user_id == current_user.id
                        ).order_by(models.MedicalImagingDiagnostic.created_at.desc()).first()
                        if latest_scan and latest_scan.recommended_specialist:
                            spec_map = {
                                "dermatologist": "Dermatology",
                                "dermatology": "Dermatology",
                                "cardiologist": "Cardiology",
                                "cardiology": "Cardiology",
                                "neurologist": "Neurology",
                                "neurology": "Neurology",
                                "pediatrician": "Pediatrics",
                                "pediatrics": "Pediatrics",
                                "general": "General Medicine"
                            }
                            spec = spec_map.get(latest_scan.recommended_specialist.lower().strip(), "")
                    action_params["specialization"] = spec
                elif "record" in p_name_lower or "prescription" in p_name_lower:
                    action_params["page_name"] = "records"
                elif "dash" in p_name_lower:
                    action_params["page_name"] = "dashboard"
                elif "setting" in p_name_lower or "profile" in p_name_lower:
                    action_params["page_name"] = "settings"
                elif "chat" in p_name_lower or "message" in p_name_lower:
                    action_params["page_name"] = "chat"
        elif action_type in ['OPEN_DOCTORS', 'find_doctors', 'book_appointment', 'bookAppointment', 'create_appointment', 'createAppointment']:
            action_type = 'openPage'
            spec = normalize_specialization(action_params.get("specialization", ""))
            if not spec and current_user.role == "patient":
                latest_scan = db.query(models.MedicalImagingDiagnostic).filter(
                    models.MedicalImagingDiagnostic.user_id == current_user.id
                ).order_by(models.MedicalImagingDiagnostic.created_at.desc()).first()
                if latest_scan and latest_scan.recommended_specialist:
                    spec_map = {
                        "dermatologist": "Dermatology",
                        "dermatology": "Dermatology",
                        "cardiologist": "Cardiology",
                        "cardiology": "Cardiology",
                        "neurologist": "Neurology",
                        "neurology": "Neurology",
                        "pediatrician": "Pediatrics",
                        "pediatrics": "Pediatrics",
                        "general": "General Medicine"
                    }
                    spec = spec_map.get(latest_scan.recommended_specialist.lower().strip(), "")
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
        elif action_type in ['open_medical_record', 'openMedicalRecord', 'view_medical_record', 'openRecord', 'open_record']:
            action_type = 'openMedicalRecord'
        elif action_type in ['open_imaging_diagnostic', 'openImagingDiagnostic', 'view_imaging_diagnostic', 'openDiagnostic', 'open_diagnostic']:
            action_type = 'openImagingDiagnostic'

        action_payload = {
            "type": action_type,
            "parameters": action_params
        }

    # Enforce Role-Based Access Control (RBAC)
    user_role = current_user.role.lower() if current_user.role else "patient"
    role_permissions = SYSTEM_CAPABILITIES.get("roles", {}).get(user_role, {}).get("permissions", [])
    
    # Recognized actions that require permission checks
    RECOGNIZED_ACTIONS = [
        "openPage", "createAppointment", "fetchPrescription", "updatePatient",
        "triggerSOS", "logout", "setReminder", "createPrescription",
        "openMedicalRecord", "openImagingDiagnostic"
    ]
    
    if action_payload:
        act_name = action_payload["type"]
        # If it is a dummy action or unrecognized action, clear payload but do NOT raise Access Denied
        if not act_name or act_name.lower() in ["none", "null", "no_action", "no", "false", "undefined"] or act_name not in RECOGNIZED_ACTIONS:
            action_payload = None
        elif act_name not in ["logout", "triggerSOS"] and act_name not in role_permissions:
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
        "reply": message,
        "citations": citations
    }
