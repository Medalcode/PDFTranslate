import sqlite3
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
CACHE_DB = Path("data/translations_cache.db")

def init_cache():
    """Ensure the cache database exists with the correct schema."""
    CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    hash TEXT PRIMARY KEY,
                    source_text TEXT,
                    translated_text TEXT,
                    target_lang TEXT
                )
            """)
            conn.commit()
    except Exception as e:
        logger.error("Failed to initialize translation cache: %s", e)

def get_cached_translation(text: str, target_lang: str) -> str | None:
    """Retrieve a translation from the cache if it exists."""
    if not text:
        return None
    h = hashlib.sha256(f"{text}:{target_lang}".encode("utf-8")).hexdigest()
    try:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            res = conn.execute(
                "SELECT translated_text FROM translations WHERE hash = ?", 
                (h,)
            ).fetchone()
            return res[0] if res else None
    except Exception as e:
        logger.warning("Cache fetch error: %s", e)
        return None

def save_to_cache(text: str, translated_text: str, target_lang: str):
    """Save a successful translation to the cache."""
    if not text or not translated_text:
        return
    h = hashlib.sha256(f"{text}:{target_lang}".encode("utf-8")).hexdigest()
    try:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO translations (hash, source_text, translated_text, target_lang) VALUES (?, ?, ?, ?)",
                (h, text, translated_text, target_lang)
            )
            conn.commit()
    except Exception as e:
        logger.warning("Cache save error: %s", e)
