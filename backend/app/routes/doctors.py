import os
from app.timezone_helper import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app import models
from app.routes.auth import get_current_user, log_action
from app.config import UPLOADS_DIR

router = APIRouter(prefix="/doctors", tags=["Doctors"])

# --- Pydantic Schemas ---
class DoctorResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    specialization: str
    location: str
    experience_years: int
    available: bool
    contact: str
    address: Optional[str] = None
    profile_picture: Optional[str] = None
    license_document_path: Optional[str] = None
    license_number: Optional[str] = None
    rating_average: Optional[float] = 4.9
    review_count: Optional[int] = 0

    class Config:
        from_attributes = True

# --- Translation Support ---
DOCTOR_TRANSLATIONS = {
    "hi": {
        "Dr. Alice Smith": {
            "name": "डॉ. एलिस स्मिथ",
            "specialization": "हृदय रोग विज्ञान (Cardiology)",
            "location": "भवन A, कमरा 102, सिटी जनरल अस्पताल"
        },
        "Dr. Bob Johnson": {
            "name": "डॉ. बॉब जॉनसन",
            "specialization": "त्वचा विज्ञान (Dermatology)",
            "location": "स्किन केयर क्लिनिक, 45 पार्क एवेन्यू"
        },
        "Dr. Charlie Brown": {
            "name": "डॉ. चार्ली ब्राउन",
            "specialization": "सामान्य चिकित्सा (General Medicine)",
            "location": "सुइट 300, मेडिकल प्लाजा"
        },
        "Dr. Diana Prince": {
            "name": "डॉ. डायना प्रिंस",
            "specialization": "न्यूरोलॉजी (Neurology)",
            "location": "न्यूरोसाइंस सेंटर, 88 ग्रैंड सेंट"
        },
        "Dr. Evan Wright": {
            "name": "डॉ. एवन राइट",
            "specialization": "बाल रोग विज्ञान (Pediatrics)",
            "location": "चिल्ड्रन क्लिनिक, 12 मेपल सेंट"
        }
    },
    "te": {
        "Dr. Alice Smith": {
            "name": "డా. ఆలిస్ స్మిత్",
            "specialization": "గుండె జబ్బుల నిపుణులు (Cardiology)",
            "location": "బిల్డింగ్ A, రూమ్ 102, సిటీ జనరల్ హాస్పిటల్"
        },
        "Dr. Bob Johnson": {
            "name": "డా. బాబ్ జాన్సన్",
            "specialization": "చర్మవ్యాధి నిపుణులు (Dermatology)",
            "location": "స్కిన్ కేర్ క్లినిక్, 45 పార్క్ అవెన్యూ"
        },
        "Dr. Charlie Brown": {
            "name": "డా. చార్లీ బ్రౌన్",
            "specialization": "జనరల్ మెడిసిన్ (General Medicine)",
            "location": "సూట్ 300, మెడికల్ ప్లాజా"
        },
        "Dr. Diana Prince": {
            "name": "డా. డయానా ప్రిన్స్",
            "specialization": "నరాల వ్యాధుల నిపుణులు (Neurology)",
            "location": "న్యూరోసైన్స్ సెంటర్, 88 గ్రాండ్ సెయింట్"
        },
        "Dr. Evan Wright": {
            "name": "డా. ఇవాన్ రైట్",
            "specialization": "పిల్లల వైద్య నిపుణులు (Pediatrics)",
            "location": "చిల్డ్రన్స్ క్లినిక్, 12 మేపుల్ సెయింట్"
        }
    }
}

DYNAMIC_TRANSLATIONS_CACHE = {
    "hi": {},
    "te": {}
}

def fallback_rule_based(name: str, specialization: str, location: str, lang: str) -> dict:
    spec_trans = {
        "hi": {
            "Cardiology": "हृदय रोग विज्ञान (Cardiology)",
            "Dermatology": "त्वचा विज्ञान (Dermatology)",
            "General Medicine": "सामान्य चिकित्सा (General Medicine)",
            "Neurology": "न्यूरोलॉजी (Neurology)",
            "Pediatrics": "बाल रोग विज्ञान (Pediatrics)",
        },
        "te": {
            "Cardiology": "గుండె జబ్బుల నిపుణులు (Cardiology)",
            "Dermatology": "చర్మవ్యాధి నిపుణులు (Dermatology)",
            "General Medicine": "జనరల్ మెడిసిన్ (General Medicine)",
            "Neurology": "నరాల వ్యాధుల నిపుణులు (Neurology)",
            "Pediatrics": "పిల్లల వైద్య నిపుణులు (Pediatrics)",
        }
    }
    
    translated_name = name
    if name.lower().startswith("dr."):
        prefix = "डॉ. " if lang == "hi" else "డా. "
        rest_of_name = name[3:].strip()
        translated_name = prefix + rest_of_name
    elif name.lower().startswith("dr"):
        prefix = "डॉ. " if lang == "hi" else "డా. "
        rest_of_name = name[2:].strip()
        translated_name = prefix + rest_of_name
        
    translated_spec = spec_trans.get(lang, {}).get(specialization, specialization)
    
    return {
        "name": translated_name,
        "specialization": translated_spec,
        "location": location
    }

def translate_text_via_llm(name: str, specialization: str, location: str, lang: str) -> dict:
    import httpx
    import os
    import json
    
    lang_name = "Hindi" if lang == "hi" else "Telugu"
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    groq_key = os.getenv("GROQ_API_KEY", "")
    hf_key = os.getenv("HUGGINGFACE_API_KEY", os.getenv("HF_API_KEY", ""))
    
    prompt = (
        f"You are a translator. Translate the following doctor details to {lang_name}.\n"
        f"Doctor Name: {name}\n"
        f"Specialization: {specialization}\n"
        f"Location: {location}\n"
        f"Return a JSON object with 'name', 'specialization', and 'location' keys. "
        f"Translate names phonetically so they sound correct and natural in {lang_name} script (not roman script). "
        f"Translate specializations and locations accurately. Do not include any explanations."
    )
    
    # 1. Primary: Gemini 2.5 Flash
    if gemini_key and not gemini_key.startswith("your_"):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            with httpx.Client() as client:
                res = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": {
                                "type": "OBJECT",
                                "properties": {
                                    "name": {"type": "STRING"},
                                    "specialization": {"type": "STRING"},
                                    "location": {"type": "STRING"}
                                },
                                "required": ["name", "specialization", "location"]
                            }
                        }
                    },
                    timeout=4.0
                )
                if res.status_code == 200:
                    res_obj = res.json()
                    text = res_obj.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    parsed = json.loads(text)
                    return {
                        "name": parsed.get("name", name),
                        "specialization": parsed.get("specialization", specialization),
                        "location": parsed.get("location", location)
                    }
                else:
                    print(f"Gemini translation returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Error in Gemini translation: {e}")

    # 2. Fallback 1: Groq (Llama-3.1-8b-instant)
    if groq_key and not groq_key.startswith("your_"):
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            with httpx.Client() as client:
                res = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [
                            {"role": "system", "content": "You are a translator. You must return only a JSON object matching the requested schema with name, specialization, and location. Do not include any markdown fences or explanations."},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    },
                    timeout=4.0
                )
                if res.status_code == 200:
                    res_obj = res.json()
                    text = res_obj["choices"][0]["message"].get("content", "").strip()
                    parsed = json.loads(text)
                    return {
                        "name": parsed.get("name", name),
                        "specialization": parsed.get("specialization", specialization),
                        "location": parsed.get("location", location)
                    }
                else:
                    print(f"Groq translation returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Error in Groq translation fallback: {e}")

    # 3. Fallback 2: Hugging Face (Llama-3.2-3B-Instruct)
    if hf_key and not hf_key.startswith("your_"):
        try:
            url = "https://api-inference.huggingface.co/models/meta-llama/Llama-3.2-3B-Instruct"
            hf_prompt = f"<|system|>\nYou are a translator. Translate the details to a JSON format containing 'name', 'specialization', and 'location'. Do not include explanations.\n<|user|>\n{prompt}\n<|assistant|>\n"
            with httpx.Client() as client:
                res = client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {hf_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "inputs": hf_prompt,
                        "parameters": {"max_new_tokens": 150, "temperature": 0.2}
                    },
                    timeout=5.0
                )
                if res.status_code == 200:
                    res_json = res.json()
                    if isinstance(res_json, list) and len(res_json) > 0:
                        generated = res_json[0].get("generated_text", "")
                        text = generated.split("<|assistant|>")[-1].strip() if "<|assistant|>" in generated else generated.replace(hf_prompt, "").strip()
                        import re
                        match = re.search(r'\{.*?\}', text, re.DOTALL)
                        if match:
                            parsed = json.loads(match.group(0))
                            return {
                                "name": parsed.get("name", name),
                                "specialization": parsed.get("specialization", specialization),
                                "location": parsed.get("location", location)
                            }
                else:
                    print(f"Hugging Face translation returned status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Error in Hugging Face translation fallback: {e}")

    # 4. Fallback 3: Rule-based translation
    return fallback_rule_based(name, specialization, location, lang)

def translate_doctor_info(name: str, specialization: str, location: str, lang: str) -> dict:
    if not lang or lang not in ["hi", "te"]:
        return {"name": name, "specialization": specialization, "location": location}
        
    import re
    if not name or re.search(r"[\u0900-\u097F\u0C00-\u0C7F]", name):
        return {"name": name, "specialization": specialization, "location": location}
        
    if name in DOCTOR_TRANSLATIONS[lang]:
        return DOCTOR_TRANSLATIONS[lang][name]
    elif name in DYNAMIC_TRANSLATIONS_CACHE[lang]:
        return DYNAMIC_TRANSLATIONS_CACHE[lang][name]
    else:
        trans = translate_text_via_llm(name, specialization or "General Medicine", location or "", lang)
        DYNAMIC_TRANSLATIONS_CACHE[lang][name] = trans
        return trans

def translate_doctor(doc_obj, lang: str):
    if not lang or lang not in ["hi", "te"]:
        return doc_obj
    
    is_dict = isinstance(doc_obj, dict)
    name = doc_obj.get("name") if is_dict else getattr(doc_obj, "name", None)
    specialization = doc_obj.get("specialization") if is_dict else getattr(doc_obj, "specialization", "General Medicine")
    location = doc_obj.get("location") if is_dict else getattr(doc_obj, "location", "")
    
    if not name:
        return doc_obj
        
    trans = translate_doctor_info(name, specialization, location, lang)
    
    if is_dict:
        doc_obj["name"] = trans["name"]
        doc_obj["specialization"] = trans["specialization"]
        if "location" in doc_obj:
            doc_obj["location"] = trans["location"]
    else:
        doc_obj.name = trans["name"]
        doc_obj.specialization = trans["specialization"]
        if hasattr(doc_obj, "location") and doc_obj.location is not None:
            doc_obj.location = trans["location"]
            
    return doc_obj

# --- Database Seeding Helper ---
def seed_doctors(db: Session):
    count = db.query(models.Doctor).count()
    if count == 0:
        sample_doctors = [
            models.Doctor(
                name="Dr. Alice Smith",
                specialization="Cardiology",
                location="Building A, Room 102, City General Hospital",
                experience_years=15,
                available=True,
                contact="alice.smith@hospital.com",
                license_number="MD-ALICE-15"
            ),
            models.Doctor(
                name="Dr. Bob Johnson",
                specialization="Dermatology",
                location="Skin Care Clinic, 45 Park Ave",
                experience_years=8,
                available=True,
                contact="bob.johnson@skincare.com",
                license_number="MD-BOB-8"
            ),
            models.Doctor(
                name="Dr. Charlie Brown",
                specialization="General Medicine",
                location="Suite 300, Medical Plaza",
                experience_years=12,
                available=True,
                contact="charlie.brown@medplaza.com",
                license_number="MD-CHARLIE-12"
            ),
            models.Doctor(
                name="Dr. Diana Prince",
                specialization="Neurology",
                location="Neuroscience Center, 88 Grand St",
                experience_years=20,
                available=True,
                contact="diana.prince@neurocenter.com",
                license_number="MD-DIANA-20"
            ),
            models.Doctor(
                name="Dr. Evan Wright",
                specialization="Pediatrics",
                location="Children's Clinic, 12 Maple St",
                experience_years=10,
                available=False, # Seed one as unavailable
                contact="evan.wright@childrens.com",
                license_number="MD-EVAN-10"
            )
        ]
        db.add_all(sample_doctors)
        db.commit()
        print("Doctor table successfully seeded with sample records.")

# --- Endpoints ---

@router.get("", response_model=List[DoctorResponse])
def get_doctors(
    specialization: Optional[str] = None,
    accept_language: Optional[str] = Header(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        query = db.query(models.Doctor)
        if specialization:
            # Case-insensitive partial matching
            query = query.filter(models.Doctor.specialization.ilike(f"%{specialization}%"))
        
        doctors = query.all()
        
        # Translate dynamically using available translations
        lang = "en"
        if accept_language:
            preferred = accept_language.split(",")[0].strip().lower()
            for key in DOCTOR_TRANSLATIONS.keys():
                if preferred.startswith(key):
                    lang = key
                    break

        res = []
        for d in doctors:
            d_resp = DoctorResponse.from_orm(d)
            translate_doctor(d_resp, lang)
            
            # Compute average rating & review count dynamically
            approved_feedbacks = [f for f in d.feedbacks if f.is_approved]
            if approved_feedbacks:
                d_resp.rating_average = round(sum(f.rating_doctor for f in approved_feedbacks) / len(approved_feedbacks), 1)
                d_resp.review_count = len(approved_feedbacks)
            else:
                d_resp.rating_average = 4.9 # Seed fallback
                d_resp.review_count = 0
                
            res.append(d_resp)
            
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the doctors list: {str(e)}"
        )

@router.post("/register")
async def register_doctor(
    name: str = Form(...),
    specialization: str = Form(...),
    location: str = Form(...),
    experience_years: int = Form(...),
    contact: str = Form(...),
    address: Optional[str] = Form(None),
    license_number: str = Form(...),
    license_document: UploadFile = File(...),
    profile_picture: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check if doctor profile already exists for this user
        existing = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if existing:
            raise HTTPException(status_code=400, detail="Doctor profile already exists for this user")

        # Handle license document saving (in-memory)
        import base64
        doc_ext = license_document.filename.split(".")[-1]
        doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
        doc_bytes = await license_document.read()
        
        # Save profile picture if provided (in-memory)
        pic_relative_path = None
        pic_encoded = None
        if profile_picture:
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_bytes = await profile_picture.read()
            pic_relative_path = f"/uploads/{pic_filename}"
            pic_encoded = base64.b64encode(pic_bytes).decode("utf-8")

        # Ensure doctor name starts with "Dr." prefix
        name_stripped = name.strip()
        if not name_stripped.lower().startswith("dr.") and not name_stripped.lower().startswith("dr "):
            name = f"Dr. {name_stripped}"
        else:
            name = name_stripped

        # Create Doctor entry
        new_doc = models.Doctor(
            user_id=current_user.id,
            name=name,
            specialization=specialization,
            location=location,
            experience_years=experience_years,
            contact=contact,
            address=address,
            available=False, # Must be verified/approved by admin first
            profile_picture=pic_relative_path,
            profile_picture_data=pic_encoded,
            license_document_path=f"/uploads/{doc_filename}",
            license_document_data=base64.b64encode(doc_bytes).decode("utf-8"),
            license_number=license_number,
            latitude=latitude,
            longitude=longitude
        )
        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        # Create DoctorVerification entry
        verification = models.DoctorVerification(
            doctor_id=new_doc.id,
            status="pending"
        )
        db.add(verification)
        db.commit()

        # Log action
        log_action(db, current_user.id, "REGISTER_DOCTOR_PROFILE", f"Doctor {name} profile registered under user {current_user.email}")

        return {
            "status": "success",
            "message": "Doctor profile registered successfully and is pending admin approval.",
            "doctor_id": new_doc.id
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during doctor registration: {str(e)}"
        )

@router.put("/profile")
async def update_doctor_profile(
    name: Optional[str] = Form(None),
    specialization: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    experience_years: Optional[int] = Form(None),
    contact: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    license_number: Optional[str] = Form(None),
    license_document: Optional[UploadFile] = File(None),
    profile_picture: Optional[UploadFile] = File(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
        if not doctor:
            raise HTTPException(status_code=404, detail="Doctor profile not found")

        # Update text fields if provided
        if name is not None:
            doctor.name = name
        if specialization is not None:
            doctor.specialization = specialization
        if location is not None:
            doctor.location = location
        if experience_years is not None:
            doctor.experience_years = experience_years
        if contact is not None:
            doctor.contact = contact
        if address is not None:
            doctor.address = address
        if license_number is not None:
            doctor.license_number = license_number
        if latitude is not None:
            doctor.latitude = latitude
        if longitude is not None:
            doctor.longitude = longitude

        # Update license document if provided (in-memory)
        if license_document:
            import base64
            doc_ext = license_document.filename.split(".")[-1]
            doc_filename = f"license_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{doc_ext}"
            doc_bytes = await license_document.read()
            doctor.license_document_path = f"/uploads/{doc_filename}"
            doctor.license_document_data = base64.b64encode(doc_bytes).decode("utf-8")
            
            # Since the license has changed, reset verification status to pending!
            verification = db.query(models.DoctorVerification).filter(models.DoctorVerification.doctor_id == doctor.id).first()
            if verification:
                verification.status = "pending"
                verification.submitted_at = datetime.datetime.utcnow()
            else:
                verification = models.DoctorVerification(doctor_id=doctor.id, status="pending")
                db.add(verification)
            
            doctor.available = False  # Deactivate doctor until verified again!

        # Update profile picture if provided (in-memory)
        if profile_picture:
            import base64
            pic_ext = profile_picture.filename.split(".")[-1]
            pic_filename = f"pic_{current_user.id}_{int(datetime.datetime.utcnow().timestamp())}.{pic_ext}"
            pic_bytes = await profile_picture.read()
            doctor.profile_picture = f"/uploads/{pic_filename}"
            doctor.profile_picture_data = base64.b64encode(pic_bytes).decode("utf-8")

        db.commit()
        db.refresh(doctor)

        log_action(db, current_user.id, "UPDATE_DOCTOR_PROFILE", f"Doctor {doctor.name} updated profile. License updated: {license_document is not None}")
        return {
            "status": "success",
            "message": "Doctor profile updated successfully.",
            "doctor": {
                "name": doctor.name,
                "specialization": doctor.specialization,
                "location": doctor.location,
                "available": doctor.available,
                "profile_picture": doctor.profile_picture,
                "license_document_path": doctor.license_document_path,
                "license_number": doctor.license_number,
                "latitude": doctor.latitude,
                "longitude": doctor.longitude
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- Leave Requests ---
class LeaveRequestCreate(BaseModel):
    start_date: str # YYYY-MM-DD
    end_date: str # YYYY-MM-DD
    reason: Optional[str] = None

@router.post("/leave-request")
def create_leave_request(
    data: LeaveRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
        
    try:
        start_date_obj = datetime.datetime.strptime(data.start_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

    try:
        end_date_obj = datetime.datetime.strptime(data.end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

    today = datetime.date.today()
    if start_date_obj < today + datetime.timedelta(days=2):
        raise HTTPException(status_code=400, detail="Leave must be requested at least 2 days in advance")

    if end_date_obj < start_date_obj:
        raise HTTPException(status_code=400, detail="End date must be on or after start date")

    new_request = models.LeaveRequest(
        doctor_id=doctor.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status="pending"
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)
    
    log_action(db, current_user.id, "LEAVE_REQUEST_SUBMITTED", f"Doctor {doctor.name} requested leave from {data.start_date} to {data.end_date}")
    return {"status": "success", "message": "Leave request submitted successfully", "request_id": new_request.id}

@router.get("/leave-requests")
def get_leave_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check if admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can view leave requests")
        
    requests = db.query(models.LeaveRequest).all()
    res = []
    for r in requests:
        res.append({
            "id": r.id,
            "doctor_id": r.doctor_id,
            "doctor_name": r.doctor.name,
            "specialization": r.doctor.specialization,
            "start_date": r.start_date,
            "end_date": r.end_date,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at
        })
    return res

@router.post("/leave-request/{id}/approve")
def approve_leave_request(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can approve leave requests")
        
    # Check if current_user has both roles (admin and doctor)
    is_doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first() is not None
    if is_doctor:
        raise HTTPException(status_code=403, detail="A user with both admin and doctor roles cannot approve leave requests.")

    req = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    req.status = "approved"
    
    # Set doctor as unavailable
    doctor = db.query(models.Doctor).filter(models.Doctor.id == req.doctor_id).first()
    if doctor:
        doctor.available = False
        
    # Notify doctor
    doctor_notif = models.Notification(
        user_id=doctor.user_id,
        message=f"Your leave request from {req.start_date} to {req.end_date} has been APPROVED by the administrator.",
        notification_type="general"
    )
    db.add(doctor_notif)
    
    # Cancel all booked appointments of this doctor during their leave period
    if doctor:
        affected_appts = db.query(models.Appointment).filter(
            models.Appointment.doctor_id == req.doctor_id,
            models.Appointment.status == "booked",
            models.Appointment.date >= req.start_date,
            models.Appointment.date <= req.end_date
        ).all()
        for appt in affected_appts:
            appt.status = "cancelled"
            cancellation_notif = models.Notification(
                user_id=appt.patient_id,
                message=f"Your appointment with {doctor.name} on {appt.date} at {appt.time} has been cancelled because the doctor is on approved leave.",
                notification_type="general"
            )
            db.add(cancellation_notif)
            
    db.commit()
    log_action(db, current_user.id, "LEAVE_REQUEST_APPROVED", f"Leave request {id} approved for doctor {doctor.name if doctor else 'Unknown'}")
    return {"status": "success", "message": "Leave request approved successfully"}

@router.post("/leave-request/{id}/reject")
def reject_leave_request(
    id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only administrators can reject leave requests")
        
    # Check if current_user has both roles (admin and doctor)
    is_doctor = db.query(models.Doctor).filter(models.Doctor.user_id == current_user.id).first() is not None
    if is_doctor:
        raise HTTPException(status_code=403, detail="A user with both admin and doctor roles cannot reject leave requests.")

    req = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
        
    req.status = "rejected"
    
    # Notify doctor
    doctor = db.query(models.Doctor).filter(models.Doctor.id == req.doctor_id).first()
    if doctor:
        doctor_notif = models.Notification(
            user_id=doctor.user_id,
            message=f"Your leave request from {req.start_date} to {req.end_date} has been REJECTED by the administrator.",
            notification_type="general"
        )
        db.add(doctor_notif)
        
    db.commit()
    log_action(db, current_user.id, "LEAVE_REQUEST_REJECTED", f"Leave request {id} rejected for doctor {doctor.name if doctor else 'Unknown'}")
    return {"status": "success", "message": "Leave request rejected successfully"}

# --- Urgent Surgery Replacement ---
@router.post("/{doctor_id}/trigger-surgery-replacement")
def trigger_surgery_replacement(
    doctor_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    doctor = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    # Check permissions (doctor themselves or admin)
    if current_user.role != "admin" and doctor.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to trigger surgery replacement for this doctor")
        
    # Fetch all booked appointments of this doctor
    appointments = db.query(models.Appointment).filter(
        models.Appointment.doctor_id == doctor_id,
        models.Appointment.status == "booked"
    ).all()
    
    # Find other doctors in the same department
    other_doctors = db.query(models.Doctor).filter(
        models.Doctor.specialization == doctor.specialization,
        models.Doctor.id != doctor_id,
        models.Doctor.available == True
    ).all()
    
    # Ensure doctor's user_id is populated if None
    if not doctor.user_id:
        doc_user = db.query(models.User).filter(models.User.email == doctor.contact).first()
        if doc_user:
            doctor.user_id = doc_user.id
            db.commit()
            db.refresh(doctor)

    reassigned_count = 0
    not_reassigned_count = 0
    
    for appt in appointments:
        if other_doctors:
            new_doc = other_doctors[reassigned_count % len(other_doctors)]
            old_doc_name = doctor.name
            appt.doctor_id = new_doc.id
            
            # Create notifications
            patient_notif = models.Notification(
                user_id=appt.patient_id,
                message=f"Your appointment on {appt.date} at {appt.time} has been reassigned to {new_doc.name} because {old_doc_name} has an urgent surgery.",
                notification_type="general"
            )
            new_doc_notif = models.Notification(
                user_id=new_doc.user_id,
                message=f"You have been assigned a new appointment on {appt.date} at {appt.time} (reassigned from {old_doc_name} due to urgent surgery).",
                notification_type="general"
            )
            db.add(patient_notif)
            db.add(new_doc_notif)
            reassigned_count += 1
        else:
            appt.status = "pending_reschedule"
            patient_notif = models.Notification(
                user_id=appt.patient_id,
                message=f"Your appointment with {doctor.name} on {appt.date} at {appt.time} is pending reschedule as the doctor has an urgent surgery and no replacement is available.",
                notification_type="general"
            )
            db.add(patient_notif)
            not_reassigned_count += 1

    # Send private messages to affected patients if doctor's user_id exists
    if doctor.user_id:
        from sqlalchemy import or_, and_
        patient_ids = {appt.patient_id for appt in appointments}
        for p_id in patient_ids:
            conv = db.query(models.PrivateConversation).filter(
                or_(
                    and_(models.PrivateConversation.user1_id == doctor.user_id, models.PrivateConversation.user2_id == p_id),
                    and_(models.PrivateConversation.user1_id == p_id, models.PrivateConversation.user2_id == doctor.user_id)
                )
            ).first()
            if not conv:
                conv = models.PrivateConversation(
                    user1_id=doctor.user_id,
                    user2_id=p_id
                )
                db.add(conv)
                db.commit()
                db.refresh(conv)

            msg_text = f"Hello, I am writing to inform you that Dr. {doctor.name} is currently unavailable due to an urgent surgery. Your appointment has been updated accordingly."
            new_msg = models.PrivateMessage(
                conversation_id=conv.id,
                sender_id=doctor.user_id,
                content=msg_text
            )
            db.add(new_msg)

            chat_notif = models.Notification(
                user_id=p_id,
                message=f"New message from Dr. {doctor.name}: {msg_text[:50]}...",
                notification_type="chat_message",
                related_id=conv.id
            )
            db.add(chat_notif)
            
    db.commit()
    log_action(db, current_user.id, "SURGERY_REPLACEMENT_TRIGGERED", f"Doctor {doctor.name} triggered surgery replacement. Reassigned: {reassigned_count}, Rescheduled: {not_reassigned_count}")
    return {
        "status": "success",
        "reassigned": reassigned_count,
        "reassigned_count": reassigned_count,
        "pending_reschedule": not_reassigned_count
    }
