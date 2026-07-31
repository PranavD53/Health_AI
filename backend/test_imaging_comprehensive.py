import pytest
import io
import json
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.database import get_db, Base, engine
from app.routes.auth import create_access_token, get_password_hash
from app import models
from app.services.common import load_image_bytes, calculate_blur_laplacian, extract_red_hue_ratio, extract_inflammation_intensity
from app.services.skin_ai import predict_skin, SKIN_SEVERITY_SPECIALIST_MAP
from app.services.xray_ai import predict_xray, XRAY_SEVERITY_SPECIALIST_MAP
from app.services.throat_ai import predict_throat, THROAT_SEVERITY_SPECIALIST_MAP

client = TestClient(app)

@pytest.fixture(scope="module")
def test_user():
    db = next(get_db())
    email = "imaging_test_user@healthai.test"
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(
            email=email,
            password=get_password_hash("Password123!"),
            role="patient",
            base_role="patient",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture(scope="module")
def auth_headers(test_user):
    token = create_access_token({"sub": test_user.email, "role": test_user.role})
    return {"Authorization": f"Bearer {token}"}


def test_image_modes_conversion():
    """Verify common.load_image_bytes handles RGBA, L, P, and RGB modes without crashing."""
    for mode in ["RGBA", "L", "P", "RGB"]:
        img = Image.new(mode, (100, 100), color=1 if mode == "P" else "red")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        
        loaded = load_image_bytes(buf)
        assert loaded.mode == "RGB"
        assert loaded.size == (100, 100)


def test_skin_prediction_various_inputs():
    """Test skin prediction with RGBA and small images."""
    img = Image.new("RGBA", (150, 150), color=(200, 100, 100, 255))
    res = predict_skin(img)
    assert res["specialist"] == "Dermatologist"
    assert len(res["top_predictions"]) > 0
    assert "condition" in res
    assert "recommendation" in res


def test_xray_prediction_various_inputs():
    """Test chest xray prediction with grayscale image."""
    img = Image.new("L", (200, 200), color=128)
    res = predict_xray(img)
    assert res["specialist"] == "Pulmonologist"
    assert len(res["top_predictions"]) > 0
    assert res["condition"] in XRAY_SEVERITY_SPECIALIST_MAP


def test_throat_prediction_feature_boundaries():
    """Test throat feature boundaries for different inflammation thresholds."""
    # High inflammation synthetic oral image (Low green/blue, high red)
    arr = np.zeros((300, 300, 3), dtype=np.uint8)
    arr[:, :, 0] = 230  # High Red
    arr[:, :, 1] = 40   # Low Green
    arr[:, :, 2] = 40   # Low Blue
    np.random.seed(123)
    arr = np.clip(arr.astype(int) + np.random.randint(-15, 15, (300, 300, 3)), 0, 255).astype(np.uint8)
    high_red_img = Image.fromarray(arr)
    
    res = predict_throat(high_red_img)
    assert res["condition"] in ["Possible Acute Pharyngitis", "Moderate Posterior Inflammation"]
    assert res["severity"] in ["High", "Moderate"]
    assert res["specialist"] == "ENT Specialist"


def test_api_analyze_endpoint_skin(auth_headers):
    """End-to-end test of POST /imaging/analyze for Skin Condition."""
    img = Image.new("RGB", (224, 224), color="brown")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/imaging/analyze",
        headers=auth_headers,
        files={"file": ("skin_test.jpg", buf, "image/jpeg")},
        data={"scan_type": "Skin Condition"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scan_type"] == "Skin Condition"
    assert data["severity"] in ["Low", "Moderate", "High", "Critical", "Normal"]
    assert "Primary Finding:" in data["findings"]
    assert "[Diagnostic Metadata:" in data["findings"]


def test_api_analyze_endpoint_xray(auth_headers):
    """End-to-end test of POST /imaging/analyze for X-Ray / Scan."""
    img = Image.new("RGB", (224, 224), color="gray")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    response = client.post(
        "/imaging/analyze",
        headers=auth_headers,
        files={"file": ("xray_test.png", buf, "image/png")},
        data={"scan_type": "X-Ray"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scan_type"] == "X-Ray"
    assert data["recommended_specialist"] == "Pulmonologist"


def test_api_analyze_endpoint_throat_rejection(auth_headers):
    """Test POST /imaging/analyze rejecting blurry image on Throat tab with HTTP 400."""
    img = Image.new("RGB", (200, 200), color="white") # Solid white = 0 variance (blurry)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/imaging/analyze",
        headers=auth_headers,
        files={"file": ("blurry_throat.jpg", buf, "image/jpeg")},
        data={"scan_type": "Throat Redness"}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "too blurry" in detail or "expected oral/throat format" in detail


def test_api_analyze_endpoint_throat_success(auth_headers):
    """Test POST /imaging/analyze for valid Throat scan."""
    np.random.seed(99)
    arr = np.random.randint(50, 220, (300, 300, 3), dtype=np.uint8)
    arr[:, :, 0] = np.clip(arr[:, :, 0] + 90, 0, 255) # High red
    oral_img = Image.fromarray(arr)
    
    buf = io.BytesIO()
    oral_img.save(buf, format="JPEG")
    buf.seek(0)

    response = client.post(
        "/imaging/analyze",
        headers=auth_headers,
        files={"file": ("valid_throat.jpg", buf, "image/jpeg")},
        data={"scan_type": "Throat Redness"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scan_type"] == "Throat Redness"
    assert data["recommended_specialist"] == "ENT Specialist"


def test_api_get_my_diagnostics(auth_headers):
    """Test GET /imaging/my-diagnostics returns history array."""
    response = client.get("/imaging/my-diagnostics", headers=auth_headers)
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) >= 3
