import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))

# Ensure the upload directory exists
os.makedirs(UPLOADS_DIR, exist_ok=True)

SYSTEM_CAPABILITIES = {
    "voice_settings": {
        "wake_words": ["hey tars", "hello tars", "tars", "wake up"],
        "standby_commands": ["bye tars", "that's enough", "go quiet", "stand by", "go to sleep", "dismissed"]
    },
    "roles": {
        "patient": {
            "permissions": [
                "find_doctors",
                "book_appointment",
                "cancel_appointment",
                "view_records",
                "analyze_record",
                "view_dashboard",
                "view_settings",
                "view_chat",
                "lodge_complaint"
            ]
        },
        "doctor": {
            "permissions": [
                "view_dashboard",
                "view_settings",
                "view_chat",
                "view_records",
                "analyze_record",
                "create_prescription",
                "trigger_sos",
                "resolve_sos",
                "switch_role",
                "change_theme"
            ]
        },
        "admin": {
            "permissions": [
                "view_dashboard",
                "view_settings",
                "view_chat",
                "verify_doctor",
                "trigger_sos",
                "resolve_sos",
                "switch_role",
                "change_theme",
                "view_records",
                "analyze_record"
            ]
        }
    },
    "actions": {
        "find_doctors": {
            "description": "Search for doctors or find a medical specialist by their specialization.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialization": {
                        "type": "string",
                        "enum": ["cardiology", "dermatology", "general", "neurology", "pediatrics"]
                    }
                },
                "required": ["specialization"]
            },
            "requires_confirmation": False
        },
        "book_appointment": {
            "description": "Book or schedule an appointment with a doctor for a specific date and time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer"},
                    "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "time": {"type": "string", "pattern": "^\\d{2}:\\d{2}$"}
                },
                "required": ["doctor_id"]
            },
            "requires_confirmation": True
        },
        "cancel_appointment": {
            "description": "Cancel an existing booked appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer"}
                },
                "required": ["appointment_id"]
            },
            "requires_confirmation": True
        },
        "create_prescription": {
            "description": "Write, issue, or send a prescription for a patient with diagnosis, medicines list, and instructions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string"},
                    "diagnosis": {"type": "string"},
                    "medicines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "dosage": {"type": "string"},
                                "frequency": {"type": "string"},
                                "duration": {"type": "string"}
                            },
                            "required": ["name", "dosage"]
                        }
                    },
                    "instructions": {"type": "string"}
                },
                "required": ["patient_name", "diagnosis", "medicines"]
            },
            "requires_confirmation": True
        },
        "verify_doctor": {
            "description": "Approve, reject, suspend, or revoke a doctor's license verification status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["verified", "rejected", "suspended", "revoked"]}
                },
                "required": ["doctor_id", "status"]
            },
            "requires_confirmation": True
        },
        "trigger_sos": {
            "description": "Trigger an SOS emergency alert. Can escalate for a specific patient if triggered by a doctor/admin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "integer"}
                }
            },
            "requires_confirmation": True
        },
        "resolve_sos": {
            "description": "Mark an active SOS emergency alert as resolved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "alert_id": {"type": "integer"}
                },
                "required": ["alert_id"]
            },
            "requires_confirmation": True
        },
        "change_theme": {
            "description": "Change the application appearance color palette theme.",
            "parameters": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string", "enum": ["light", "dark", "teal", "purple", "rose", "custom"]}
                },
                "required": ["theme"]
            },
            "requires_confirmation": False
        },
        "switch_role": {
            "description": "Switch context/workspace mode between Admin and Doctor roles (for authorized users).",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "requires_confirmation": True
        },
        "view_records": {
            "description": "Navigate to the medical records management dashboard.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "navigation_path": "/records",
            "requires_confirmation": False
        },
        "analyze_record": {
            "description": "Scan, summarize, or explain insights for a specific medical record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "record_id": {"type": "integer"}
                },
                "required": ["record_id"]
            },
            "requires_confirmation": False
        },
        "view_settings": {
            "description": "Navigate to the settings and profile configuration page.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "navigation_path": "/settings",
            "requires_confirmation": False
        },
        "view_chat": {
            "description": "Navigate to the private chats and messages workspace.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "navigation_path": "/chat",
            "requires_confirmation": False
        },
        "view_dashboard": {
            "description": "Navigate to the main portal dashboard.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "navigation_path": "/dashboard",
            "requires_confirmation": False
        },
        "lodge_complaint": {
            "description": "Lodge/file a formal platform complaint with the administrative panel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"}
                },
                "required": ["message"]
            },
            "requires_confirmation": False
        }
    }
}

