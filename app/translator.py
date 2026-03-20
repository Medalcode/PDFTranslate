"""
Core PDF translation engine.

Pipeline: PDF → Texto estructurado → HTML → Traducción → Nuevo PDF limpio (via ReportLab)
"""
import logging
import time
import tempfile
from pathlib import Path
from io import BytesIO

import fitz  # PyMuPDF
from deep_translator import GoogleTranslator
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Image, PageBreak
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.config import SOURCE_LANG, TARGET_LANG
from app.text_classifier import classify

logger = logging.getLogger(__name__)

MAX_CHUNK = 4900  # Google Translate safe limit


# ---------------------------------------------------------------------------
# Text chunking & translation helpers
# ---------------------------------------------------------------------------

def _split_text(text: str) -> list[str]:
    """Split long text into safe chunks for the translator."""
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        wl = len(word) + 1
        if current_len + wl > MAX_CHUNK and current:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += wl
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _translate_text(text: str, translator: GoogleTranslator, max_retries: int = 3) -> str:
    """Translate a single block of text with retry logic."""
    stripped = text.strip()
    if not stripped:
        return text

    def _call(chunk: str, attempt: int = 0) -> str:
        while attempt < max_retries:
            try:
                time.sleep(0.4)
                result = translator.translate(chunk)
                return result if result else chunk
            except Exception as exc:
                attempt += 1
                logger.warning("Translation attempt %d/%d failed: %s", attempt, max_retries, exc)
                time.sleep(1.5 * attempt)
        logger.error("All retries exhausted for chunk starting with: %s…", chunk[:40])
        return chunk  # Fallback: return original

    if len(stripped) <= MAX_CHUNK:
        return _call(stripped)

    return " ".join(_call(c) for c in _split_text(stripped))


# ---------------------------------------------------------------------------
# ReportLab styles
# ---------------------------------------------------------------------------

def _build_styles():
    styles = getSampleStyleSheet()

    body = ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    )
    title = ParagraphStyle(
        "ChapterTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    code = ParagraphStyle(
        "CodeBlock",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        leftIndent=10,
        rightIndent=10,
        spaceBefore=6,
        spaceAfter=6,
        backColor=colors.HexColor("#f5f5f5"),
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=0.5,
        borderPadding=6,
    )
    caption = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        spaceAfter=4,
        textColor=colors.grey,
    )
    return {"body": body, "title": title, "code": code, "caption": caption}


# ---------------------------------------------------------------------------
# Main translate function
# ---------------------------------------------------------------------------

def translate_pdf(
    input_path: str,
    output_path: str,
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
    progress_callback=None,
) -> None:
    """
    Translate a PDF using a clean PDF → ReportLab rebuild pipeline.

    Steps:
      1. Extract text blocks and images from each page with PyMuPDF.
      2. Classify each block (code / title / body text).
      3. Translate non-code text with Google Translate.
      4. Rebuild a brand-new PDF with ReportLab (proper text flow, no overlaps).
    """
    logger.info("Starting translation: %s → %s", input_path, output_path)
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    styles = _build_styles()

    doc_in = fitz.open(input_path)
    total_pages = len(doc_in)

    story: list = []  # ReportLab flowable list

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for page_idx, page in enumerate(doc_in):
            logger.info("Processing page %d / %d", page_idx + 1, total_pages)

            # --- sort blocks top-to-bottom, left-to-right ---
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))

            for block in blocks:
                x0, y0, x1, y1, content, block_no, block_type = block

                # ── Image block ─────────────────────────────────────────────
                if block_type == 1:
                    try:
                        rect = fitz.Rect(x0, y0, x1, y1)
                        pix = page.get_pixmap(clip=rect, dpi=150)
                        img_file = tmp_path / f"img_{page_idx}_{block_no}.png"
                        pix.save(str(img_file))

                        # Scale image to fit within page margins
                        available_width = A4[0] - 4 * cm  # 2cm margin each side
                        img_w = pix.width
                        img_h = pix.height
                        if img_w > 0:
                            scale = min(available_width / img_w, 1.0)
                            draw_w = img_w * scale * (72 / 150)  # pts at 150 dpi
                            draw_h = img_h * scale * (72 / 150)
                            story.append(Image(str(img_file), width=draw_w, height=draw_h))
                            story.append(Spacer(1, 4))
                    except Exception as exc:
                        logger.warning("Could not extract image p%d b%d: %s", page_idx, block_no, exc)
                    continue

                # ── Text block ───────────────────────────────────────────────
                text = content.strip()
                if not text:
                    continue

                btype = classify(text)

                if btype == "code":
                    # Never translate; preserve whitespace
                    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Preformatted(safe, styles["code"]))

                elif btype == "title":
                    translated = _translate_text(text, translator)
                    safe = translated.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe, styles["title"]))

                else:
                    # Join broken PDF lines into a real paragraph
                    joined = " ".join(text.splitlines()).strip()
                    translated = _translate_text(joined, translator)
                    safe = translated.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(safe, styles["body"]))

            story.append(Spacer(1, 6))  # small gap between PDF pages

            if progress_callback:
                progress_callback(page_idx + 1, total_pages)

        doc_in.close()

    # --- Build the new PDF with ReportLab ---
    logger.info("Rendering new PDF with ReportLab...")
    doc_out = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    doc_out.build(story)
    logger.info("Done → %s", output_path)
