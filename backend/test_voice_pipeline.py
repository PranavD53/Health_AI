# test_voice_pipeline.py
# Integration tests for the TARS voice-native WebSocket pipeline.

import os
import json
import sys
import unittest.mock as mock

# Mock faster_whisper module to prevent load timeouts and ModuleNotFoundError
mock_faster_whisper = mock.Mock()
mock_model_inst = mock.Mock()
mock_info = mock.Mock()
mock_info.language = "en"
mock_segment = mock.Mock()
mock_segment.text = "Hello. I need help."
mock_model_inst.transcribe.return_value = ([mock_segment], mock_info)
mock_faster_whisper.WhisperModel.return_value = mock_model_inst
sys.modules["faster_whisper"] = mock_faster_whisper
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["TESTING"] = "True"
os.environ["SECRET_KEY"] = os.environ.get("SECRET_KEY", "test_secret_key_12345")

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


import time

def setup_module():
    app.dependency_overrides[get_db] = override_get_db
    t0 = time.time()
    print(f"\n[TIMING] setup_module started")
    
    t1 = time.time()
    Base.metadata.create_all(bind=engine)
    print(f"[TIMING] Base.metadata.create_all took {time.time() - t1:.2f}s")
    
    t2 = time.time()
    _cleanup_db(engine, Base)
    print(f"[TIMING] _cleanup_db took {time.time() - t2:.2f}s")
    
    t3 = time.time()
    db = TestingSessionLocal()
    try:
        from app.routes.auth import get_password_hash
        # Seed ONLY the single patient user needed for this test to minimize network roundtrips to Supabase
        patient_user = models.User(
            email="patient@healthai.test",
            password=get_password_hash("Password123!"),
            role="patient",
            base_role="patient",
            has_admin_permission=False,
            is_active=True,
            is_verified=True,
        )
        db.add(patient_user)
        db.commit()
        db.refresh(patient_user)

        profile = models.PatientProfile(
            user_id=patient_user.id,
            name="Sarah Johnson",
            date_of_birth="1994-04-18",
            gender="Female",
            height=165,
            weight=62,
        )
        db.add(profile)
        db.commit()
    finally:
        db.close()
    print(f"[TIMING] Seeding took {time.time() - t3:.2f}s")
    print(f"[TIMING] setup_module completed in {time.time() - t0:.2f}s")

def teardown_module():
    t0 = time.time()
    print(f"\n[TIMING] teardown_module started")
    global engine
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]
    engine.dispose()
    print(f"[TIMING] teardown_module completed in {time.time() - t0:.2f}s")

# Mock async iterator for streaming lines
class AsyncIterator:
    def __init__(self, items):
        self.items = items
    def __aiter__(self):
        return self
    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)

# Mock context manager for httpx.AsyncClient.stream
class MockStreamResponse:
    def __init__(self, lines):
        self.status_code = 200
        self.lines = lines
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    def aiter_lines(self):
        return AsyncIterator(self.lines)

def test_voice_websocket_pipeline():
    t_start = time.time()
    t_login = time.time()
    # 1. Login user to get auth token
    login_resp = client.post("/auth/login", json={
        "email": "patient@healthai.test",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    print(f"[TIMING] Login took {time.time() - t_login:.2f}s")

    # Mock Whisper API and LLM response
    mock_whisper_resp = mock.Mock()
    mock_whisper_resp.status_code = 200
    mock_whisper_resp.json.return_value = {"text": "Hello. I need help."}

    mock_lines = [
        'data: {"type": "chunk", "content": "Hello! I am TARS. "}',
        'data: {"type": "chunk", "content": "How can I assist you today?"}',
        'data: [DONE]'
    ]
    mock_stream = MockStreamResponse(mock_lines)

    # Mock piper_tts to yield dummy PCM audio bytes as async generator
    async def mock_synthesize(text, lang="en"):
        yield b"PCM_AUDIO_SAMPLE_DATA_CHUNK"

    t_ws = time.time()
    with mock.patch("httpx.AsyncClient.post", return_value=mock_whisper_resp), \
         mock.patch("httpx.AsyncClient.stream", return_value=mock_stream), \
         mock.patch("app.routes.voice_socket.synthesize_speech_stream", side_effect=mock_synthesize):

        # Connect to WebSocket
        with client.websocket_connect(f"/ws/tars/voice?token={token}") as ws:
            # Send speech start trigger
            ws.send_json({"type": "speech_start"})
            
            # Send dummy audio bytes
            ws.send_bytes(b"DUMMY_PCM_DATA_CHUNKS_OF_SPEECH" * 50)
            
            # Send speech stop trigger to process
            ws.send_json({
                "type": "speech_stop",
                "groq_key": "gsk_mock_key_for_testing"
            })

            # Assert that we receive transcription first
            transcription_msg = ws.receive_json()
            assert transcription_msg["type"] == "transcription"
            assert transcription_msg["text"] == "Hello. I need help."
            assert transcription_msg["language"] == "en"

            # Next, we should receive LLM text chunks and audio streams
            chunk_counter = 0
            audio_start_counter = 0
            audio_end_counter = 0
            received_binary = False

            try:
                while True:
                    msg = ws.receive()
                    if "bytes" in msg:
                        assert msg["bytes"] == b"PCM_AUDIO_SAMPLE_DATA_CHUNK"
                        received_binary = True
                    elif "text" in msg:
                        text_data = msg["text"]
                        if text_data.startswith("data: ") or "chunk" in text_data:
                            # SSE line or JSON chunk message
                            chunk_counter += 1
                        else:
                            control = json.loads(text_data)
                            if control.get("type") == "audio_start":
                                audio_start_counter += 1
                            elif control.get("type") == "audio_end":
                                audio_end_counter += 1
                                # Break out of loop since audio streaming has finished
                                break
            except Exception:
                # WebSocket closes or receives disconnect
                pass

            # Verify we received streaming text and corresponding Piper audio streams
            assert chunk_counter > 0
            assert audio_start_counter > 0
            assert audio_end_counter > 0
            assert received_binary is True
    print(f"[TIMING] WebSocket operations took {time.time() - t_ws:.2f}s")
            
    print("\n=== TARS VOICE WS PIPELINE TEST COMPLETED SUCCESSFULLY ===")
    print(f"[TIMING] Total test function execution took {time.time() - t_start:.2f}s")

if __name__ == "__main__":
    test_voice_websocket_pipeline()
