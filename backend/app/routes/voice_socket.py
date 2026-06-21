# voice_socket.py
# WebSocket endpoint to handle voice-native dialogue.

import os
import io
import wave
import json
import logging
import re
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from app.routes.auth import SECRET_KEY, ALGORITHM
from jose import jwt
import httpx
from app.services.piper_tts import synthesize_speech_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/tars", tags=["TARS Voice WebSocket"])

@router.websocket("/voice")
async def voice_websocket(websocket: WebSocket, token: Optional[str] = None, db: Session = Depends(get_db)):
    # Accept the connection
    await websocket.accept()
    
    # 1. Authenticate user from token (passed in query params or headers)
    current_user = None
    try:
        if not token:
            token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token")
            return
            
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token payload")
            return
            
        current_user = db.query(models.User).filter(models.User.email == email).first()
        if not current_user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="User not found")
            return
    except Exception as e:
        logger.error(f"WS Auth error: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=f"Authentication failed: {str(e)}")
        return

    # Buffer to accumulate incoming raw PCM bytes
    audio_buffer = io.BytesIO()
    
    try:
        while True:
            # Wait for messages from client
            message = await websocket.receive()
            
            if "bytes" in message:
                # Raw PCM bytes (Int16, 16kHz mono)
                audio_buffer.write(message["bytes"])
                
            elif "text" in message:
                # Control signal from client
                control = json.loads(message["text"])
                msg_type = control.get("type")
                
                if msg_type == "speech_start":
                    # Clear buffer to start fresh recording
                    audio_buffer = io.BytesIO()
                    
                elif msg_type == "speech_stop":
                    # Extract accumulated audio data
                    audio_data = audio_buffer.getvalue()
                    audio_buffer = io.BytesIO() # Reset buffer
                    
                    if len(audio_data) < 1000:
                        await websocket.send_json({"type": "error", "message": "Audio input too short"})
                        continue
                        
                    # Convert raw PCM bytes into a WAV in-memory structure
                    wav_io = io.BytesIO()
                    with wave.open(wav_io, "wb") as wav_file:
                        wav_file.setnchannels(1)       # Mono
                        wav_file.setsampwidth(2)       # 16-bit PCM
                        wav_file.setframerate(16000)   # 16kHz
                        wav_file.writeframes(audio_data)
                    
                    wav_bytes = wav_io.getvalue()
                    
                    # 2. Transcribe Audio
                    transcription = ""
                    detected_language = "en"
                    
                    # Prioritize Groq Whisper API (Cloud-based, <200ms) to eliminate local CPU latency
                    groq_key = os.getenv("GROQ_API_KEY", "") or control.get("groq_key", "")
                    if groq_key and not groq_key.startswith("your_groq_api_key"):
                        try:
                            async with httpx.AsyncClient() as client:
                                files = {"file": ("voice.wav", wav_bytes, "audio/wav")}
                                headers = {"Authorization": f"Bearer {groq_key}"}
                                response = await client.post(
                                    "https://api.groq.com/openai/v1/audio/transcriptions",
                                    headers=headers,
                                    files=files,
                                    data={"model": "whisper-large-v3"}
                                )
                                if response.status_code == 200:
                                    res_json = response.json()
                                    transcription = res_json.get("text", "").strip()
                                    
                                    # Simple language check from text
                                    if re.search(r'[\u0C00-\u0C7F]', transcription):
                                        detected_language = "te"
                                    elif re.search(r'[\u0900-\u097F]', transcription):
                                        detected_language = "hi"
                                    else:
                                        detected_language = "en"
                                else:
                                    logger.error(f"Groq transcription error: {response.text}")
                        except Exception as groq_e:
                            logger.error(f"Groq transcription request failed: {groq_e}")
                            
                    # Only fall back to local faster-whisper if Groq failed or key is missing
                    if not transcription:
                        try:
                            from faster_whisper import WhisperModel
                            model = WhisperModel("tiny", device="cpu", compute_type="int8")
                            wav_io.seek(0)
                            segments, info = model.transcribe(wav_io, beam_size=5)
                            transcription = "".join(seg.text for seg in segments).strip()
                            detected_language = info.language
                        except Exception as local_e:
                            logger.error(f"Local faster-whisper failed: {local_e}")
                            await websocket.send_json({"type": "error", "message": "Voice transcription failed"})
                            continue

                    if not transcription:
                        await websocket.send_json({"type": "error", "message": "Silence or unintelligible speech."})
                        continue

                    # Send transcription immediately to update frontend chat UI
                    await websocket.send_json({
                        "type": "transcription",
                        "text": transcription,
                        "language": detected_language
                    })
                    
                    # 3. Stream Response from TARS LLM Assistant
                    groq_key = control.get("groq_key") or ""
                    hf_key = control.get("hf_key") or ""
                    gemini_key = control.get("gemini_key") or ""
                    
                    from app.services.tars_engine import execute_tars_intent
                    
                    try:
                        result = await execute_tars_intent(
                            message=transcription,
                            current_user=current_user,
                            db=db,
                            gemini_key=gemini_key,
                            groq_key=groq_key,
                            hf_key=hf_key,
                            language=detected_language
                        )
                        
                        accumulated_text = result["message"]
                        action_payload = result["action"]
                        disclaimer = result["disclaimer"]
                        
                        # Send text representation of the assistant response to client
                        # To simulate typing or streaming chunks, we yield chunk events
                        chunk_size = 4
                        for i in range(0, len(accumulated_text), chunk_size):
                            chunk = accumulated_text[i:i+chunk_size]
                            await websocket.send_json({
                                "type": "chunk",
                                "content": chunk
                            })
                            await asyncio.sleep(0.01)
                            
                        # Send final action mapping to complete the call execution on frontend
                        await websocket.send_json({
                            "type": "action",
                            "action": action_payload,
                            "disclaimer": disclaimer,
                            "reply": accumulated_text
                        })
                        
                        # Stream TTS audio sentences to client
                        import asyncio
                        spoken_index = 0
                        sentence_regex = re.compile(r'[^.?!।\n]+[.?!।\n]+')
                        
                        pending_text = accumulated_text
                        for match in sentence_regex.finditer(pending_text):
                            sentence = match.group(0).strip()
                            if sentence:
                                await websocket.send_json({"type": "audio_start", "text": sentence})
                                for audio_chunk in synthesize_speech_stream(sentence, detected_language):
                                    await websocket.send_bytes(audio_chunk)
                                await websocket.send_json({"type": "audio_end"})
                            spoken_index += match.end()
                            
                        # Speak any remaining text
                        remaining = accumulated_text[spoken_index:].strip()
                        if remaining:
                            await websocket.send_json({"type": "audio_start", "text": remaining})
                            for audio_chunk in synthesize_speech_stream(remaining, detected_language):
                                await websocket.send_bytes(audio_chunk)
                            await websocket.send_json({"type": "audio_end"})
                    except Exception as tars_e:
                        logger.error(f"Voice WebSocket engine error: {tars_e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Query execution failed: {str(tars_e)}"
                        })
                            
    except WebSocketDisconnect:
        logger.info("Voice WebSocket disconnected cleanly")
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
