import json
import os
from typing import Tuple

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "self_care_whitelist.json")

def load_whitelist() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

SELF_CARE_WHITELIST = load_whitelist()

def is_self_care_eligible(symptom_category: str) -> Tuple[bool, str]:
    """
    Pure function: checks if symptom category is eligible for self care.
    Returns (eligible: bool, precaution_text: str)
    """
    if not symptom_category:
        return False, ""
        
    category_data = SELF_CARE_WHITELIST.get(symptom_category, None)
    
    if not category_data:
        # Fallback to OTHER
        category_data = SELF_CARE_WHITELIST.get("OTHER", {"eligible": False, "precautions": "Please consult a doctor."})
        
    return category_data.get("eligible", False), category_data.get("precautions", "Please consult a doctor.")
