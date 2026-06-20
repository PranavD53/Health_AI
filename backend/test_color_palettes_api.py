import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test_secret_key_12345")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# Wait, let's add the root workspace directory
import sys
sys.path.insert(0, "c:\\Users\\srich\\OneDrive\Desktop\\Health_AI")

from app.main import app
from app.database import Base, get_db, engine, SessionLocal as TestingSessionLocal
from app import models

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def _cleanup_db(engine, Base):
    from sqlalchemy.orm import close_all_sessions
    try:
        close_all_sessions()
    except Exception:
        pass
    if "sqlite" in str(engine.url):
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception:
            pass
    else:
        from sqlalchemy import text
        tables = [t.name for t in Base.metadata.sorted_tables]
        if tables:
            tables_str = ", ".join(f'"{t}"' for t in tables)
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE"))
            except Exception as e:
                print(f"Cleanup truncate skipped: {e}")


def setup_db():
    Base.metadata.create_all(bind=engine)
    _cleanup_db(engine, Base)
    db = TestingSessionLocal()
    try:
        # Create a test user
        from app.routes.auth import get_password_hash
        user = models.User(
            email="test_user@healthai.test",
            password=get_password_hash("Password123!"),
            role="patient",
            base_role="patient",
            is_active=True,
            is_verified=True
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

def run_tests():
    setup_db()
    print("Database set up successfully. Logging in...")

    # Log in
    login_response = client.post("/auth/login", json={
        "email": "test_user@healthai.test",
        "password": "Password123!"
    })
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("Logged in successfully. Testing GET /palettes...")

    # 1. GET /palettes (should be empty initially)
    get_res = client.get("/palettes", headers=headers)
    assert get_res.status_code == 200, f"GET failed: {get_res.text}"
    data = get_res.json()
    assert data["active"] is None, "Expected active palette to be None initially"
    assert len(data["history"]) == 0, "Expected empty history initially"
    print("  GET /palettes returned empty as expected.")

    # 2. POST /palettes (Save a custom palette)
    print("Testing POST /palettes (Save custom palette)...")
    palette_payload = {
        "primary_color": "#112233",
        "secondary_color": "#445566",
        "background_color": "#778899",
        "accent_color": "#aabbcc"
    }
    post_res = client.post("/palettes", json=palette_payload, headers=headers)
    assert post_res.status_code == 201, f"POST failed: {post_res.text}"
    saved_palette = post_res.json()
    assert saved_palette["primary_color"] == "#112233"
    assert saved_palette["is_active"] is True
    print("  POST /palettes successfully saved active palette.")

    # 3. GET /palettes again
    print("Testing GET /palettes again to verify active palette is returned...")
    get_res = client.get("/palettes", headers=headers)
    assert get_res.status_code == 200, f"GET failed: {get_res.text}"
    data = get_res.json()
    assert data["active"] is not None, "Expected active palette to be present"
    assert data["active"]["primary_color"] == "#112233"
    assert len(data["history"]) == 1, f"Expected 1 item in history, got {len(data['history'])}"
    print("  GET /palettes correctly returned active palette.")

    # 4. Save a second palette and verify deactivation of the first
    print("Testing saving a second palette to check atomicity/is_active toggling...")
    palette_payload_2 = {
        "primary_color": "#998877",
        "secondary_color": "#665544",
        "background_color": "#332211",
        "accent_color": "#ccbbaa"
    }
    post_res_2 = client.post("/palettes", json=palette_payload_2, headers=headers)
    assert post_res_2.status_code == 201, f"POST 2 failed: {post_res_2.text}"
    
    get_res = client.get("/palettes", headers=headers)
    data = get_res.json()
    assert data["active"]["primary_color"] == "#998877", "Expected new palette to be active"
    
    # Confirm history length is 2 and only 1 is active
    assert len(data["history"]) == 2, f"Expected history size 2, got {len(data['history'])}"
    active_count = sum(1 for p in data["history"] if p["is_active"])
    assert active_count == 1, f"Expected exactly 1 active palette, got {active_count}"
    print("  Palette toggling and history insertion work perfectly!")

    # 5. Activate the first palette again
    first_palette_id = saved_palette["id"]
    print(f"Testing POST /palettes/activate/{first_palette_id}...")
    act_res = client.post(f"/palettes/activate/{first_palette_id}", headers=headers)
    assert act_res.status_code == 200, f"Activate failed: {act_res.text}"
    
    get_res = client.get("/palettes", headers=headers)
    data = get_res.json()
    assert data["active"]["primary_color"] == "#112233", "Expected first palette to become active again"
    print("  Palette activation from history works perfectly!")

    print("\nAll color palette API tests PASSED successfully!")

if __name__ == "__main__":
    run_tests()
