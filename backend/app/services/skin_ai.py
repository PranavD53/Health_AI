"""
Skin Condition AI Service

Model Specification (Step 0 Pre-Implementation Verification):
- Repository ID: LaurianeMD/vit-skin-disease
- Base Architecture: Vision Transformer (ViT-Base patch16-224 fine-tuned)
- Class List (22 categories):
    0: 'Acne', 1: 'Actinic Keratosis', 2: 'Benign Tumors', 3: 'Bullous',
    4: 'Candidiasis', 5: 'Drug Eruption', 6: 'Eczema', 7: 'Infestations Bites',
    8: 'Lichen', 9: 'Lupus', 10: 'Moles', 11: 'Psoriasis', 12: 'Rosacea',
    13: 'Seborrh Keratoses', 14: 'Skin Cancer', 15: 'Sun Sunlight Damage',
    16: 'Tinea', 17: 'Unknown Normal', 18: 'Vascular Tumors', 19: 'Vasculitis',
    20: 'Vitiligo', 21: 'Warts'
- Training Context & Datasets: Fine-tuned on dermatological imaging subsets (HAM10000, ISIC, DermNet).
- Reported Metrics & Limitations: Top-1 accuracy ~75-80%, Top-3 ~90%. Limitations include sensitivity to illumination, focus, and variation in skin tone.
- License: Open-source (Apache-2.0 / MIT compatible)
- Expected Input Preprocessing: RGB 224x224, standard ViT normalization (mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]).
"""

import logging
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForImageClassification, AutoConfig
from app.services.common import load_image_bytes

logger = logging.getLogger(__name__)

SKIN_MODEL_ID = "LaurianeMD/vit-skin-disease"

# Singleton reference
_skin_model = None
_skin_config = None

# Step 4: Complete mapping table covering every class produced by LaurianeMD/vit-skin-disease
SKIN_SEVERITY_SPECIALIST_MAP = {
    "Acne": {
        "severity": "Moderate",
        "recommendation": "Maintain gentle cleansing, apply non-comedogenic OTC treatments, and consult a dermatologist if inflammatory cysts develop.",
        "specialist": "Dermatologist"
    },
    "Actinic Keratosis": {
        "severity": "High",
        "recommendation": "Pre-cancerous sun damage requires professional dermatological evaluation and topical or cryotherapy management.",
        "specialist": "Dermatologist"
    },
    "Benign Tumors": {
        "severity": "Low",
        "recommendation": "Monitor for changes in size, shape, or color during routine dermatological checkups.",
        "specialist": "Dermatologist"
    },
    "Bullous": {
        "severity": "High",
        "recommendation": "Blistering condition requires prompt dermatological evaluation to prevent secondary infection and tissue damage.",
        "specialist": "Dermatologist"
    },
    "Candidiasis": {
        "severity": "Moderate",
        "recommendation": "Keep skin dry and clean. Consider OTC topical antifungal cream and consult a dermatologist if persistent.",
        "specialist": "Dermatologist"
    },
    "Drug Eruption": {
        "severity": "High",
        "recommendation": "Discontinue suspected allergic medication under medical guidance and seek urgent dermatological assessment.",
        "specialist": "Dermatologist"
    },
    "Eczema": {
        "severity": "Moderate",
        "recommendation": "Apply hydrating emollients regularly, avoid harsh detergents, and consult a dermatologist for anti-inflammatory care.",
        "specialist": "Dermatologist"
    },
    "Infestations Bites": {
        "severity": "Low",
        "recommendation": "Apply soothing calamine or mild hydrocortisone cream. Monitor for signs of secondary bacterial infection.",
        "specialist": "Dermatologist"
    },
    "Lichen": {
        "severity": "Moderate",
        "recommendation": "Avoid scratching affected areas. Consult a dermatologist for topical steroid evaluation.",
        "specialist": "Dermatologist"
    },
    "Lupus": {
        "severity": "High",
        "recommendation": "Cutaneous autoimmune manifestation requires comprehensive specialist diagnosis and photo-protection.",
        "specialist": "Dermatologist"
    },
    "Moles": {
        "severity": "Low",
        "recommendation": "Perform regular ABCDE mole self-checks and schedule periodic professional skin examinations.",
        "specialist": "Dermatologist"
    },
    "Psoriasis": {
        "severity": "Moderate",
        "recommendation": "Keep skin well-moisturized with emollients or OTC coal tar preparations; consult dermatologist for systemic care.",
        "specialist": "Dermatologist"
    },
    "Rosacea": {
        "severity": "Moderate",
        "recommendation": "Avoid facial heat, sun exposure, and dietary triggers. Consult dermatologist for topical metronidazole therapy.",
        "specialist": "Dermatologist"
    },
    "Seborrh Keratoses": {
        "severity": "Low",
        "recommendation": "Benign skin growth. Consult a dermatologist if lesion becomes irritated or for cosmetic removal.",
        "specialist": "Dermatologist"
    },
    "Skin Cancer": {
        "severity": "High",
        "recommendation": "Urgent dermatological consultation required for professional dermoscopy, biopsy, and treatment planning.",
        "specialist": "Dermatologist"
    },
    "Sun Sunlight Damage": {
        "severity": "Low",
        "recommendation": "Apply broad-spectrum SPF 30+ sunscreen daily, wear protective apparel, and hydrate skin.",
        "specialist": "Dermatologist"
    },
    "Tinea": {
        "severity": "Moderate",
        "recommendation": "Apply OTC topical antifungal cream twice daily for 2 to 4 weeks and maintain dry hygiene.",
        "specialist": "Dermatologist"
    },
    "Unknown Normal": {
        "severity": "Low",
        "recommendation": "No obvious acute dermatological lesion detected. Continue routine skin care and sunscreen protection.",
        "specialist": "Dermatologist"
    },
    "Vascular Tumors": {
        "severity": "Moderate",
        "recommendation": "Schedule clinical examination to assess vascular lesion stability and rule out vascular anomalies.",
        "specialist": "Dermatologist"
    },
    "Vasculitis": {
        "severity": "High",
        "recommendation": "Cutaneous vascular inflammation requires comprehensive medical and dermatological evaluation.",
        "specialist": "Dermatologist"
    },
    "Vitiligo": {
        "severity": "Moderate",
        "recommendation": "Consult a dermatologist for phototherapy or topical repigmentation options and maintain rigorous sun protection.",
        "specialist": "Dermatologist"
    },
    "Warts": {
        "severity": "Low",
        "recommendation": "Consider OTC salicylic acid preparations or consult a dermatologist for cryotherapy.",
        "specialist": "Dermatologist"
    }
}

DEFAULT_SKIN_MAPPING = {
    "severity": "Moderate",
    "recommendation": "Consult a dermatologist for a professional clinical skin evaluation.",
    "specialist": "Dermatologist"
}


def load_skin_model():
    """Startup model singleton loader."""
    global _skin_model, _skin_config
    try:
        logger.info(f"Loading Skin AI model: {SKIN_MODEL_ID}...")
        _skin_config = AutoConfig.from_pretrained(SKIN_MODEL_ID)
        _skin_model = AutoModelForImageClassification.from_pretrained(SKIN_MODEL_ID)
        _skin_model.eval()
        logger.info(f"Skin AI model {SKIN_MODEL_ID} loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load Skin AI model '{SKIN_MODEL_ID}': {e}")
        _skin_model = None
        _skin_config = None


def get_skin_model():
    """Returns singleton model instance."""
    global _skin_model
    if _skin_model is None:
        load_skin_model()
    return _skin_model, _skin_config


def preprocess(pil_image: Image.Image) -> torch.Tensor:
    """Standardized preprocessing for ViT-Skin model."""
    resized = pil_image.resize((224, 224))
    arr = np.array(resized).astype(np.float32) / 255.0
    mean = np.array([0.5, 0.5, 0.5])
    std = np.array([0.5, 0.5, 0.5])
    norm = (arr - mean) / std
    tensor = torch.from_numpy(norm.transpose(2, 0, 1)).float().unsqueeze(0)
    return tensor


def infer(tensor: torch.Tensor, model, config) -> list:
    """Runs model forward pass and returns top-3 predicted label indices & confidence scores."""
    with torch.no_grad():
        outputs = model(tensor)
        logits = outputs.logits[0]
        probs = torch.softmax(logits, dim=-1)
        top_k = torch.topk(probs, k=min(3, probs.size(0)))
        
        top_indices = top_k.indices.tolist()
        top_probs = top_k.values.tolist()
        
        results = []
        id2label = config.id2label if config and hasattr(config, "id2label") else {}
        for idx, score in zip(top_indices, top_probs):
            label_name = id2label.get(idx, f"Class_{idx}")
            results.append({
                "label": label_name,
                "confidence": round(score * 100, 2)
            })
        return results


def postprocess(predictions: list) -> dict:
    """Maps raw top predictions through severity/specialist lookup table into standardized dict."""
    formatted_top = []
    for pred in predictions:
        lbl = pred["label"]
        conf = pred["confidence"]
        map_info = SKIN_SEVERITY_SPECIALIST_MAP.get(lbl, DEFAULT_SKIN_MAPPING)
        formatted_top.append({
            "label": lbl,
            "confidence": conf,
            "severity": map_info["severity"],
            "recommendation": map_info["recommendation"],
            "specialist": map_info["specialist"]
        })

    top_1 = formatted_top[0] if formatted_top else {
        "label": "Unknown Normal",
        "confidence": 0.0,
        "severity": "Low",
        "recommendation": "Practice routine skin care.",
        "specialist": "Dermatologist"
    }

    return {
        "condition": top_1["label"],
        "confidence": top_1["confidence"],
        "severity": top_1["severity"],
        "specialist": top_1["specialist"],
        "recommendation": top_1["recommendation"],
        "top_predictions": formatted_top
    }


def predict_skin(image_input) -> dict:
    """Public standard entry point for Skin predictions."""
    model, config = get_skin_model()
    if model is None:
        raise RuntimeError("Skin Diagnostics Model temporarily unavailable")

    pil_img = load_image_bytes(image_input)
    tensor = preprocess(pil_img)
    raw_preds = infer(tensor, model, config)
    return postprocess(raw_preds)
