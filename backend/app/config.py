import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.environ.get("UPLOADS_DIR", os.path.join(BASE_DIR, "uploads"))

# Ensure the upload directory exists
os.makedirs(UPLOADS_DIR, exist_ok=True)
