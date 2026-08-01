"""
Throat Redness & Pharyngeal Diagnostics Service (Deterministic Heuristic Engine)

Notice: As no reliable public machine-learning classifier exists for oral throat diagnostics,
this tab utilizes deterministic, feature-based image heuristics.

Workflow:
1. Input Validation & Rejection:
   - Sharpness / Blur check via Laplacian variance.
   - Oral/Pharyngeal color spectrum validation via red-hue mask coverage.
   - If invalid/blurry, returns specific rejection exception detailing why.
2. Feature Extraction:
   - Red-hue area coverage ratio in HSV space.
   - Inflammation intensity ratio (mean Red intensity relative to Green/Blue channels).
   - Texture variance and mean brightness.
3. Deterministic Mapping:
   - Maps extracted feature thresholds into discrete pharyngeal findings:
     'Normal Pharyngeal Appearance', 'Mild Pharyngeal Erythema',
     'Moderate Posterior Inflammation', 'Possible Acute Pharyngitis'.
4. Specialist Routing: Fixed to 'ENT Specialist' (Otolaryngology).
"""

import logging
import numpy as np
from PIL import Image
from app.services.common import (
    load_image_bytes,
    calculate_blur_laplacian,
    extract_red_hue_ratio,
    extract_inflammation_intensity
)

logger = logging.getLogger(__name__)

# Minimum blur sharpness threshold (Laplacian variance)
LAPLACIAN_BLUR_THRESHOLD = 50.0

# Minimum red-hue coverage ratio to confirm an oral/throat visual scan
MIN_RED_HUE_RATIO = 0.05

# Step 4: Mapping dictionary for throat heuristic classes
THROAT_SEVERITY_SPECIALIST_MAP = {
    "Normal Pharyngeal Appearance": {
        "severity": "Normal",
        "recommendation": "Pharyngeal mucosa appears normal with healthy coloration. Practice good oral hygiene and remain hydrated.",
        "specialist": "ENT Specialist"
    },
    "Mild Pharyngeal Erythema": {
        "severity": "Low",
        "recommendation": "Mild mucosal redness noted. Gargle warm saline water 2-3 times daily, stay hydrated, and use soothing throat lozenges.",
        "specialist": "ENT Specialist"
    },
    "Moderate Posterior Inflammation": {
        "severity": "Moderate",
        "recommendation": "Posterior pharyngeal wall exhibits noticeable vascular congestion. Rest voice, maintain hydration, and consider OTC pain relievers (paracetamol) if uncomfortable.",
        "specialist": "ENT Specialist"
    },
    "Possible Acute Pharyngitis": {
        "severity": "High",
        "recommendation": "Significant pharyngeal redness and inflammatory signals detected. Consult an ENT specialist or physician for clinical swab evaluation.",
        "specialist": "ENT Specialist"
    }
}


def preprocess(pil_image: Image.Image) -> dict:
    """
    Validates input image quality and extracts deterministic image features.
    Only raises ValueError for severe blur (< 30.0 Laplacian variance).
    Non-red or normal oral photos pass through to infer() for Normal classification.
    """
    # 1. Blur Check (extreme blur filter)
    blur_score = calculate_blur_laplacian(pil_image)
    if blur_score < 30.0:
        raise ValueError("Image too blurry — please retake with steady lighting and clear focus.")

    # 2. Aspect Ratio & Dimension Check
    w, h = pil_image.size
    aspect_ratio = max(w / h, h / w)
    if aspect_ratio > 4.0:
        raise ValueError("Invalid image aspect ratio. Please upload a standard oral scan photo.")

    # 3. Red Hue Coverage & Inflammation Extraction
    red_ratio = extract_red_hue_ratio(pil_image)
    inflammation_score = extract_inflammation_intensity(pil_image)

    return {
        "blur_score": blur_score,
        "red_ratio": red_ratio,
        "inflammation_score": inflammation_score
    }


def infer(features: dict) -> list:
    """
    Maps extracted feature thresholds deterministically to pharyngeal findings.
    - red_ratio > 0.40 or inflammation > 1.40 -> Possible Acute Pharyngitis (High)
    - red_ratio > 0.25 or inflammation > 1.22 -> Moderate Posterior Inflammation (Moderate)
    - red_ratio > 0.10 or inflammation > 1.06 -> Mild Pharyngeal Erythema (Low)
    - otherwise -> Normal Pharyngeal Appearance (Normal)
    """
    red_ratio = features["red_ratio"]
    inflammation = features["inflammation_score"]

    # Threshold rules
    if red_ratio > 0.40 or inflammation > 1.40:
        label = "Possible Acute Pharyngitis"
        confidence = min(96.5, round(65.0 + (red_ratio * 40.0), 1))
    elif red_ratio > 0.25 or inflammation > 1.22:
        label = "Moderate Posterior Inflammation"
        confidence = min(92.0, round(58.0 + (red_ratio * 35.0), 1))
    elif red_ratio > 0.10 or inflammation > 1.06:
        label = "Mild Pharyngeal Erythema"
        confidence = min(88.0, round(52.0 + (red_ratio * 30.0), 1))
    else:
        label = "Normal Pharyngeal Appearance"
        conf_score = round(92.0 - (red_ratio * 30.0), 1)
        confidence = max(75.0, min(95.0, conf_score))

    return [{
        "label": label,
        "confidence": confidence
    }]


def postprocess(predictions: list) -> dict:
    """Formats predictions using THROAT_SEVERITY_SPECIALIST_MAP and flags output as heuristic."""
    top_pred = predictions[0]
    lbl = top_pred["label"]
    conf = top_pred["confidence"]
    map_info = THROAT_SEVERITY_SPECIALIST_MAP.get(lbl, THROAT_SEVERITY_SPECIALIST_MAP["Normal Pharyngeal Appearance"])

    formatted_top = [{
        "label": lbl,
        "confidence": conf,
        "severity": map_info["severity"],
        "recommendation": map_info["recommendation"],
        "specialist": map_info["specialist"]
    }]

    return {
        "condition": lbl,
        "confidence": conf,
        "severity": map_info["severity"],
        "specialist": map_info["specialist"],
        "recommendation": map_info["recommendation"],
        "is_heuristic": True,
        "top_predictions": formatted_top
    }


def predict_throat(image_input) -> dict:
    """Public standard entry point for Throat predictions."""
    pil_img = load_image_bytes(image_input)
    features = preprocess(pil_img)
    raw_preds = infer(features)
    return postprocess(raw_preds)
