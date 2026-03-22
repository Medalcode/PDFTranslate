import os
from dotenv import load_dotenv

load_dotenv()

SOURCE_LANG: str = os.getenv("SOURCE_LANG", "en")
TARGET_LANG: str = os.getenv("TARGET_LANG", "es")
UPLOAD_DIR: str  = os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR: str  = os.getenv("OUTPUT_DIR", "outputs")

# ── LLM Configuration (optional — vastly improves translation quality) ────────
# Provider: "gemini" | "openai" | "custom" (OpenAI-compatible)
LLM_PROVIDER: str  = os.getenv("LLM_PROVIDER", "gemini")
LLM_API_KEY: str   = os.getenv("LLM_API_KEY", "")
LLM_MODEL: str     = os.getenv("LLM_MODEL", "")       # empty = provider default
LLM_BASE_URL: str  = os.getenv("LLM_BASE_URL", "")    # for custom/local endpoints

# Ensure runtime directories exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
