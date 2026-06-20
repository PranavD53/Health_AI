# piper_tts.py
# Service to run local Piper TTS engine via subprocess and stream audio bytes.

import os
import subprocess
import shutil
import logging
from typing import Generator

logger = logging.getLogger(__name__)

# Default Piper Model configurations (downloaded models would be stored here)
PIPER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "piper_models")
os.makedirs(PIPER_DIR, exist_ok=True)

# Voice models mapping
# If models exist locally, they will be loaded. Otherwise, falls back to text-only mode
VOICE_MODELS = {
    "en": "en_US-lessac-medium.onnx",
    "hi": "hi_IN-fenil-medium.onnx",
    "te": "te_IN-gita-medium.onnx" # Example hypothetical Telugu model name
}

def get_piper_executable() -> str | None:
    """Finds the piper executable on the system path or inside local PIPER_DIR."""
    # 1. Check system PATH
    exe = shutil.which("piper")
    if exe:
        return exe
        
    # 2. Check local directories (for custom local installations)
    local_paths = [
        os.path.join(PIPER_DIR, "piper"),
        os.path.join(PIPER_DIR, "piper.exe"),
        "piper",
        "piper.exe"
    ]
    for p in local_paths:
        if os.path.exists(p):
            return p
            
    return None

def synthesize_speech_stream(text: str, language: str = "en") -> Generator[bytes, None, None]:
    """
    Synthesizes the given text using Piper TTS and yields raw 16kHz 16-bit mono PCM bytes.
    If Piper is not configured or fails, yields empty bytes.
    """
    if not text.strip():
        return

    piper_exe = get_piper_executable()
    if not piper_exe:
        logger.warning("Piper TTS executable not found. Audio synthesis skipped.")
        return

    # Resolve language model
    lang_code = language.split("-")[0].lower()
    model_name = VOICE_MODELS.get(lang_code, VOICE_MODELS["en"])
    model_path = os.path.join(PIPER_DIR, model_name)

    if not os.path.exists(model_path):
        logger.warning(f"Piper model for '{lang_code}' not found at {model_path}. Audio synthesis skipped.")
        return

    try:
        # Piper CLI syntax: piper -m model.onnx --output_raw
        # This will write raw 16kHz 16-bit mono PCM bytes to stdout
        cmd = [
            piper_exe,
            "-m", model_path,
            "--output_raw"
        ]
        
        # Start subprocess
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        
        # Write text to stdin to initiate synthesis
        process.stdin.write(text.encode("utf-8") + b"\n")
        process.stdin.close()
        
        # Yield stdout raw PCM chunks of 1024 bytes (512 samples)
        while True:
            chunk = process.stdout.read(1024)
            if not chunk:
                break
            yield chunk
            
        process.wait()
        
    except Exception as e:
        logger.error(f"Piper synthesis subprocess error: {e}")
        return
