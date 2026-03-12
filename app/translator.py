"""
Core PDF translation engine.
Translates a PDF file block-by-block while preserving layout and images.
"""

import os
import logging
from pathlib import Path

import fitz  # PyMuPDF
from deep_translator import GoogleTranslator

from app.config import SOURCE_LANG, TARGET_LANG
from app.text_classifier import classify

logger = logging.getLogger(__name__)

TEMP_IMG_DIR = "temp_images"
os.makedirs(TEMP_IMG_DIR, exist_ok=True)

# Max chars GoogleTranslator can handle per request
MAX_CHUNK = 4900


def _split_text(text: str) -> list[str]:
    """Split long text into chunks that fit within the translator limit."""
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        word_len = len(word) + 1
        if current_len + word_len > MAX_CHUNK and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += word_len
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _translate_text(text: str, translator: GoogleTranslator) -> str:
    """Translate text, handling long blocks by splitting into chunks."""
    stripped = text.strip()
    if not stripped:
        return text
    try:
        if len(stripped) <= MAX_CHUNK:
            result = translator.translate(stripped)
            return result if result else text
        # Split and translate each chunk, then join
        chunks = _split_text(stripped)
        translated_chunks = []
        for chunk in chunks:
            result = translator.translate(chunk)
            translated_chunks.append(result if result else chunk)
        return " ".join(translated_chunks)
    except Exception as exc:
        logger.warning("Translation failed for block: %s", exc)
        return text


def _translate_block(text: str, translator: GoogleTranslator) -> str:
    """Classify a block and translate (or skip) accordingly."""
    block_type = classify(text)
    if block_type == "code":
        return text  # Never translate code
    translated = _translate_text(text, translator)
    if block_type == "title":
        return translated.upper()
    return translated


def translate_pdf(
    input_path: str,
    output_path: str,
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
    progress_callback=None,
) -> None:
    """
    Open input_path PDF, translate all text blocks page-by-page,
    preserve images, and save to output_path.
    """
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    doc = fitz.open(input_path)
    new_doc = fitz.open()
    total_pages = len(doc)

    for page_index, page in enumerate(doc):
        logger.info("Translating page %d / %d", page_index + 1, total_pages)

        new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)

        # ── 1. Re-insert images from the original page ─────────────────────
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")

                # Find the image's bounding box on the page
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue

                img_path = os.path.join(TEMP_IMG_DIR, f"img_{page_index}_{xref}.{image_ext}")
                with open(img_path, "wb") as f:
                    f.write(image_bytes)

                for rect in img_rects:
                    new_page.insert_image(rect, filename=img_path)
            except Exception as exc:
                logger.warning("Could not insert image xref=%d: %s", xref, exc)

        # ── 2. Translate and place text blocks ─────────────────────────────
        blocks = page.get_text("blocks")  # returns (x0, y0, x1, y1, text, block_no, block_type)
        for block in blocks:
            x0, y0, x1, y1, text, _block_no, block_type = block

            # block_type 1 = image block (already handled above)
            if block_type == 1 or not text.strip():
                continue

            try:
                # Get font size from the first span on this block for reference
                span_dict = page.get_text("dict", clip=fitz.Rect(x0, y0, x1, y1))
                font_size = 10.0
                for blk in span_dict.get("blocks", []):
                    for line in blk.get("lines", []):
                        for span in line.get("spans", []):
                            size = span.get("size", 10.0)
                            if size > 0:
                                font_size = size
                                break
                        break
                    break
                font_size = max(6.0, min(font_size, 12.0))  # clamp
            except Exception:
                font_size = 10.0

            translated = _translate_block(text, translator)
            rect = fitz.Rect(x0, y0, x1, y1)

            try:
                new_page.insert_textbox(
                    rect,
                    translated,
                    fontsize=font_size,
                    fontname="helv",
                    align=fitz.TEXT_ALIGN_LEFT,
                )
            except Exception as exc:
                # Fallback: insert at top-left of block
                try:
                    new_page.insert_text((x0, y0 + font_size), translated, fontsize=font_size)
                except Exception:
                    logger.warning("Could not insert text block: %s", exc)

        # Report progress
        if progress_callback:
            progress_callback(page_index + 1, total_pages)

    new_doc.save(output_path, deflate=True, garbage=4)
    new_doc.close()
    doc.close()
    logger.info("Saved translated PDF to %s", output_path)
