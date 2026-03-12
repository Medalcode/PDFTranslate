import os
from dotenv import load_dotenv

load_dotenv()

SOURCE_LANG: str = os.getenv("SOURCE_LANG", "en")
TARGET_LANG: str = os.getenv("TARGET_LANG", "es")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR: str = os.getenv("OUTPUT_DIR", "outputs")

# Ensure directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("temp_images", exist_ok=True)
