import pytest
import numpy as np
from PIL import Image
from app.services.skin_ai import predict_skin, SKIN_SEVERITY_SPECIALIST_MAP
from app.services.xray_ai import predict_xray, XRAY_SEVERITY_SPECIALIST_MAP
from app.services.throat_ai import predict_throat, THROAT_SEVERITY_SPECIALIST_MAP

def test_skin_prediction():
    # Test valid RGB image
    img = Image.new('RGB', (224, 224), color='blue')
    res = predict_skin(img)
    
    assert "condition" in res
    assert "confidence" in res
    assert "severity" in res
    assert res["specialist"] == "Dermatologist"
    assert "recommendation" in res
    assert "top_predictions" in res
    assert len(res["top_predictions"]) <= 3
    
    # Verify mapping table covers all returned classes
    for pred in res["top_predictions"]:
        assert pred["label"] in SKIN_SEVERITY_SPECIALIST_MAP
        assert pred["severity"] in ["Low", "Moderate", "High", "Critical", "Normal"]
        assert pred["specialist"] == "Dermatologist"


def test_xray_prediction():
    # Test valid grayscale radiograph mock
    img = Image.new('RGB', (224, 224), color='gray')
    res = predict_xray(img)
    
    assert "condition" in res
    assert "confidence" in res
    assert "severity" in res
    assert res["specialist"] == "Pulmonologist"
    assert "recommendation" in res
    assert "top_predictions" in res
    assert len(res["top_predictions"]) <= 3

    for pred in res["top_predictions"]:
        assert pred["label"] in XRAY_SEVERITY_SPECIALIST_MAP
        assert pred["specialist"] == "Pulmonologist"


def test_throat_prediction_valid():
    # Textured oral image simulation
    np.random.seed(42)
    arr = np.random.randint(50, 220, (300, 300, 3), dtype=np.uint8)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + 80, 0, 255) # Oral red hue
    oral_img = Image.fromarray(arr)
    
    res = predict_throat(oral_img)
    assert res["is_heuristic"] is True
    assert res["specialist"] == "ENT Specialist"
    assert res["condition"] in THROAT_SEVERITY_SPECIALIST_MAP


def test_throat_prediction_rejection():
    # Blurry image should trigger clear rejection ValueError
    blur_img = Image.new('RGB', (200, 200), color='white')
    with pytest.raises(ValueError) as excinfo:
        predict_throat(blur_img)
    
    assert "too blurry" in str(excinfo.value) or "expected oral/throat format" in str(excinfo.value)
