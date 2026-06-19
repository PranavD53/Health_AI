import json
import os
import re
from typing import Optional, Dict, Any, Tuple

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "lab_test_whitelist.json")

def load_whitelist() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

LAB_TEST_WHITELIST = load_whitelist()

def classify_test_type(text: str) -> Optional[str]:
    """
    Pure function: classify_test_type(extracted_text) -> str | None
    Classifies the test type based on the presence of marker keywords.
    """
    if not text:
        return None
        
    text_lower = text.lower()
    
    best_match = None
    max_matches = 0
    THRESHOLD = 3 # minimum keyword matches required
    
    for test_type, config in LAB_TEST_WHITELIST.items():
        markers = config.get("marker_keywords", [])
        matches = 0
        for marker in markers:
            if marker.lower() in text_lower:
                matches += 1
                
        # If test type has very few markers, adjust threshold
        effective_threshold = min(THRESHOLD, len(markers))
        
        if matches >= effective_threshold and matches > max_matches:
            best_match = test_type
            max_matches = matches
            
    return best_match

def parse_lab_values(text: str, test_type: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """
    Parses specific lab values using regex from the whitelist config.
    Returns (parsed_values_dict, flags_dict)
    """
    if test_type not in LAB_TEST_WHITELIST:
        return {}, {}
        
    parameters = LAB_TEST_WHITELIST[test_type].get("parameters", {})
    parsed_values = {}
    flags = {}
    
    for param_name, param_config in parameters.items():
        pattern = param_config.get("pattern", "")
        if not pattern:
            continue
            
        match = re.search(pattern, text)
        if match:
            try:
                val_str = match.group(1).strip()
                val_float = float(val_str)
                
                # Check normal range
                normal_range = param_config.get("normal_range", [])
                flag = "NORMAL"
                if len(normal_range) == 2:
                    if val_float < normal_range[0]:
                        flag = "LOW"
                    elif val_float > normal_range[1]:
                        flag = "HIGH"
                
                parsed_values[param_name] = {
                    "value": val_float,
                    "unit": param_config.get("unit", "")
                }
                if flag != "NORMAL":
                    flags[param_name] = flag
            except ValueError:
                pass
                
    return parsed_values, flags
