import json
import os
import re
from typing import Tuple, List

# Load emergency keywords from config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "emergency_keywords.json")

def load_keywords() -> List[str]:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return ["chest pain", "stroke", "heart attack", "unconscious", "bleeding"]

EMERGENCY_KEYWORDS = load_keywords()

def detect_emergency(text: str) -> Tuple[bool, List[str]]:
    """
    Pure function: detect_emergency(text) -> (bool, list[str])
    Returns True and a list of matched keywords if any emergency keywords are found.
    """
    if not text:
        return False, []
    
    text_lower = text.lower()
    matched_terms = []
    
    for kw in EMERGENCY_KEYWORDS:
        # Simple regex word boundary match
        pattern = r"\b" + re.escape(kw.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched_terms.append(kw)
            
    if matched_terms:
        return True, matched_terms
        
    return False, []
