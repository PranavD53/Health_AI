"""
Chest X-Ray AI Diagnostics Service

Model Specification (Step 0 Pre-Implementation Verification):
- Repository ID: hiroaki-f/my_chest_xray_model
- Base Architecture: Vision Transformer (ViT-Base patch16-224 fine-tuned)
- Class List (14 multi-label pathology categories from NIH ChestX-ray14):
    0: 'Atelectasis', 1: 'Cardiomegaly', 2: 'Effusion', 3: 'Infiltration',
    4: 'Mass', 5: 'Nodule', 6: 'Pneumonia', 7: 'Pneumothorax', 8: 'Consolidation',
    9: 'Edema', 10: 'Emphysema', 11: 'Fibrosis', 12: 'Pleural_Thickening', 13: 'Hernia'
- Training Context & Datasets: NIH ChestX-ray14 dataset (112,120 frontal chest X-ray images).
- Reported Metrics & Limitations: Multi-label classification with independent Sigmoid outputs per class. Mean AUC ~0.80 across 14 findings. Limitations include overlap in 2D projection opacities and false positive rate for mild infiltration.
- License: Open-source (Apache-2.0)
- Expected Input Preprocessing: RGB 224x224, standard ImageNet normalization (mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]).
"""

import logging
import torch
import numpy as np
from PIL import Image
from transformers import AutoModelForImageClassification, AutoConfig
from app.services.common import load_image_bytes

logger = logging.getLogger(__name__)

XRAY_MODEL_ID = "hiroaki-f/my_chest_xray_model"

# Singleton reference
_xray_model = None
_xray_config = None

# Step 4: Complete mapping table covering every output class of hiroaki-f/my_chest_xray_model
XRAY_SEVERITY_SPECIALIST_MAP = {
    "Atelectasis": {
        "severity": "Moderate",
        "recommendation": "Partial pulmonary collapse noted. Perform deep breathing exercises and consult a pulmonologist.",
        "specialist": "Pulmonologist"
    },
    "Cardiomegaly": {
        "severity": "High",
        "recommendation": "Enlarged cardiac silhouette observed. Seek prompt pulmonology and cardiology evaluation.",
        "specialist": "Pulmonologist"
    },
    "Effusion": {
        "severity": "High",
        "recommendation": "Pleural fluid accumulation detected. Pulmonology consultation and clinical correlation strongly advised.",
        "specialist": "Pulmonologist"
    },
    "Infiltration": {
        "severity": "Moderate",
        "recommendation": "Pulmonary airspace opacity identified. Consult pulmonologist for infectious or inflammatory workup.",
        "specialist": "Pulmonologist"
    },
    "Mass": {
        "severity": "High",
        "recommendation": "Focal pulmonary mass lesion detected. Urgent chest CT scan and pulmonologist evaluation required.",
        "specialist": "Pulmonologist"
    },
    "Nodule": {
        "severity": "Moderate",
        "recommendation": "Solitary or multiple pulmonary nodular opacities detected. Follow-up imaging and pulmonologist review advised.",
        "specialist": "Pulmonologist"
    },
    "Pneumonia": {
        "severity": "High",
        "recommendation": "Infectious parenchymal consolidation suggested. Consult pulmonologist for antibiotic therapy and clinical management.",
        "specialist": "Pulmonologist"
    },
    "Pneumothorax": {
        "severity": "High",
        "recommendation": "Air in the pleural space identified. Seek immediate clinical assessment and emergency pulmonology evaluation.",
        "specialist": "Pulmonologist"
    },
    "Consolidation": {
        "severity": "High",
        "recommendation": "Airspace consolidation detected. Prompt pulmonology consultation and clinical correlation recommended.",
        "specialist": "Pulmonologist"
    },
    "Edema": {
        "severity": "High",
        "recommendation": "Pulmonary vascular congestion/edema indicated. Urgent medical and pulmonology evaluation required.",
        "specialist": "Pulmonologist"
    },
    "Emphysema": {
        "severity": "Moderate",
        "recommendation": "Chronic hyperinflation findings consistent with emphysema. Consult pulmonologist for spirometry testing.",
        "specialist": "Pulmonologist"
    },
    "Fibrosis": {
        "severity": "Moderate",
        "recommendation": "Interstitial fibrotic changes observed. Pulmonology evaluation advised to monitor lung volumes.",
        "specialist": "Pulmonologist"
    },
    "Pleural_Thickening": {
        "severity": "Moderate",
        "recommendation": "Pleural thickening noted. Consult pulmonologist for clinical correlation.",
        "specialist": "Pulmonologist"
    },
    "Hernia": {
        "severity": "High",
        "recommendation": "Diaphragmatic herniation suspected. Specialist clinical consultation recommended.",
        "specialist": "Pulmonologist"
    },
    "NORMAL": {
        "severity": "Normal",
        "recommendation": "No acute focal pulmonary consolidation, pleural effusion, or pneumothorax detected.",
        "specialist": "Pulmonologist"
    }
}

DEFAULT_XRAY_MAPPING = {
    "severity": "Moderate",
    "recommendation": "Consult a pulmonologist for a clinical radiograph review.",
    "specialist": "Pulmonologist"
}


def load_xray_model():
    """Startup model singleton loader."""
    global _xray_model, _xray_config
    try:
        logger.info(f"Loading Chest X-Ray AI model: {XRAY_MODEL_ID}...")
        _xray_config = AutoConfig.from_pretrained(XRAY_MODEL_ID)
        _xray_model = AutoModelForImageClassification.from_pretrained(XRAY_MODEL_ID)
        _xray_model.eval()
        logger.info(f"Chest X-Ray AI model {XRAY_MODEL_ID} loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load Chest X-Ray AI model '{XRAY_MODEL_ID}': {e}")
        _xray_model = None
        _xray_config = None


def get_xray_model():
    """Returns singleton model instance."""
    global _xray_model
    if _xray_model is None:
        load_xray_model()
    return _xray_model, _xray_config


def preprocess(pil_image: Image.Image) -> torch.Tensor:
    """Standardized preprocessing for Chest X-Ray ViT model."""
    resized = pil_image.resize((224, 224))
    arr = np.array(resized).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406])
    std = np.array([0.229, 0.224, 0.225])
    norm = (arr - mean) / std
    tensor = torch.from_numpy(norm.transpose(2, 0, 1)).float().unsqueeze(0)
    return tensor


def infer(tensor: torch.Tensor, model, config) -> list:
    """
    Runs model forward pass using Sigmoid activation for independent multi-label probabilities.
    Returns top-3 independent highest probability conditions.
    """
    with torch.no_grad():
        outputs = model(tensor)
        logits = outputs.logits[0]
        # Multi-label probability: Sigmoid activation per class
        probs = torch.sigmoid(logits)
        
        top_k = torch.topk(probs, k=min(3, probs.size(0)))
        top_indices = top_k.indices.tolist()
        top_probs = top_k.values.tolist()
        
        results = []
        id2label = config.id2label if config and hasattr(config, "id2label") else {}
        for idx, score in zip(top_indices, top_probs):
            label_name = id2label.get(idx, f"Condition_{idx}")
            results.append({
                "label": label_name,
                "confidence": round(score * 100, 2)
            })
        return results


def postprocess(predictions: list) -> dict:
    """Maps raw predictions through severity/specialist lookup table into standardized dict."""
    formatted_top = []
    for pred in predictions:
        lbl = pred["label"]
        conf = pred["confidence"]
        map_info = XRAY_SEVERITY_SPECIALIST_MAP.get(lbl, DEFAULT_XRAY_MAPPING)
        formatted_top.append({
            "label": lbl,
            "confidence": conf,
            "severity": map_info["severity"],
            "recommendation": map_info["recommendation"],
            "specialist": map_info["specialist"]
        })

    top_1 = formatted_top[0] if formatted_top else {
        "label": "NORMAL",
        "confidence": 0.0,
        "severity": "Normal",
        "recommendation": "No acute focal pulmonary consolidation detected.",
        "specialist": "Pulmonologist"
    }

    return {
        "condition": top_1["label"],
        "confidence": top_1["confidence"],
        "severity": top_1["severity"],
        "specialist": top_1["specialist"],
        "recommendation": top_1["recommendation"],
        "top_predictions": formatted_top
    }


def predict_xray(image_input) -> dict:
    """Public standard entry point for Chest X-Ray predictions."""
    model, config = get_xray_model()
    if model is None:
        raise RuntimeError("Chest X-Ray Diagnostics Model temporarily unavailable")

    pil_img = load_image_bytes(image_input)
    tensor = preprocess(pil_img)
    raw_preds = infer(tensor, model, config)
    return postprocess(raw_preds)
