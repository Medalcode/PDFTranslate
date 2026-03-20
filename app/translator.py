"""
Core PDF translation engine.

Pipeline: PDF → Bloques estructurados → Traducción por lotes → Nuevo PDF limpio (ReportLab)
"""
import logging
import re
import time
import tempfile
from pathlib import Path

import fitz  # PyMuPDF
from deep_translator import GoogleTranslator
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted, Image, PageBreak
from reportlab.lib.enums import TA_JUSTIFY

from app.config import SOURCE_LANG, TARGET_LANG
from app.text_classifier import classify

logger = logging.getLogger(__name__)

MAX_CHUNK = 4500          # conservative Google Translate limit per call
BATCH_SEP = " 🔹 "        # unique separator for batch calls (emoji not translated)
BATCH_MAX = 3000          # max total chars per batch API call
API_DELAY = 1.2           # seconds between API calls

# ---------------------------------------------------------------------------
# Technical terms that must NEVER be translated
# ---------------------------------------------------------------------------
PROTECTED = {
    # Apache ecosystem
    "Hadoop", "HDFS", "YARN", "MapReduce", "Spark", "Hive", "Pig",
    "Flume", "Sqoop", "HBase", "ZooKeeper", "Avro", "Parquet", "Crunch",
    "Oozie", "Tez", "Kafka", "Storm", "Flink", "Cassandra", "MongoDB",
    "Nutch", "ADAM", "Oozie", "Thrift",
    # Cloud / infra
    "AWS", "S3", "EC2", "GCS", "Azure", "Docker", "Kubernetes",
    # Languages / tools
    "Java", "Python", "Scala", "Ruby", "Maven", "Gradle", "Git",
    "MRUnit", "Kerberos", "WebHDFS", "HttpFS",
    # Formats / protocols
    "JSON", "XML", "CSV", "HTTP", "REST", "JDBC", "ODBC", "SQL",
    "ISBN", "API", "IDE", "GFS", "DAG", "UDF", "UDAF", "IDL",
    # Social / branding — prevent literal translations
    "Twitter", "Facebook", "YouTube", "LinkedIn", "GitHub", "Safari",
    "O'Reilly", "Cloudera", "Apache", "Peachpit", "Syngress",
    # Currency / country abbreviations
    "US", "UK", "CAN",
}

_PH_START = "PROT"          # placeholder prefix
_ph_map: dict[str, str] = {}

# Soft-hyphen and hyphenated-line-break cleanup
_SOFT_HYPHEN = re.compile(r"\xad")          # soft hyphen (0xAD)
_HYPHEN_BREAK = re.compile(r"-(\n)\s*")    # word- \n word → join
_BULLET_GLYPH = re.compile(r"[\u25a0\u25cf\u2022\u2023]")  # ■ ● • ‣


def _clean_block(text: str) -> str:
    """Remove PDF artefacts: soft hyphens, bad hyphenated line-breaks, bullet glyphs."""
    text = _SOFT_HYPHEN.sub("", text)
    text = _HYPHEN_BREAK.sub("", text)
    text = _BULLET_GLYPH.sub("\u2022 ", text)
    return text


_TOC_ENTRY = re.compile(
    r"(\.{3,}|\s\d{1,4}\s*$)",
    re.MULTILINE,
)


def _split_block_lines(text: str) -> list[str]:
    """
    For TOC blocks, return each line separately so they render as individual
    entries. A block is TOC-like when ≥2 of its lines have dot-leaders or
    trailing page numbers.
    For normal prose, returns a single joined string.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) <= 1:
        return [text.strip()]

    toc_count = sum(1 for l in lines if _TOC_ENTRY.search(l))
    if toc_count >= 2:
        return lines  # keep structure

    return [" ".join(lines)]  # join prose paragraph


def _protect(text: str) -> tuple[str, dict[str, str]]:
    """Replace protected terms with unique placeholders."""
    ph_map: dict[str, str] = {}
    idx = 0
    for term in PROTECTED:
        # match whole-word (case-sensitive)
        pattern = r"\b" + re.escape(term) + r"\b"
        placeholder = f"{_PH_START}{idx:03d}X"
        if re.search(pattern, text):
            text = re.sub(pattern, placeholder, text)
            ph_map[placeholder] = term
            idx += 1
    return text, ph_map


def _restore(text: str, ph_map: dict[str, str]) -> str:
    """Restore protected terms from placeholders."""
    for ph, original in ph_map.items():
        text = text.replace(ph, original)
    return text


# ---------------------------------------------------------------------------
# Translation helpers
# ---------------------------------------------------------------------------

def _call_api(text: str, translator: GoogleTranslator, max_retries: int = 4) -> str:
    """Single call to the translation API with exponential-backoff retry."""
    for attempt in range(max_retries):
        try:
            time.sleep(API_DELAY)
            result = translator.translate(text)
            if result:
                return result
            logger.warning("API returned None on attempt %d, retrying…", attempt + 1)
        except Exception as exc:
            wait = 2 ** attempt
            logger.warning("API error attempt %d/%d (%s). Waiting %ds…",
                           attempt + 1, max_retries, exc, wait)
            time.sleep(wait)
    logger.error("All retries exhausted. Returning original text.")
    return text


def _translate_chunk(text: str, translator: GoogleTranslator) -> str:
    """Protect terms, translate, restore."""
    protected_text, ph_map = _protect(text)
    translated = _call_api(protected_text, translator)
    return _restore(translated, ph_map)


def _translate_batch(texts: list[str], translator: GoogleTranslator) -> list[str]:
    """
    Translate a list of strings in as few API calls as possible by batching.
    Uses a unique separator that Google won't translate.
    """
    if not texts:
        return texts

    results: list[str] = []
    batch: list[str] = []
    batch_len = 0

    def flush(batch: list[str]) -> list[str]:
        if not batch:
            return []
        joined = BATCH_SEP.join(batch)
        protected_joined, ph_map = _protect(joined)
        translated_joined = _call_api(protected_joined, translator)
        translated_joined = _restore(translated_joined, ph_map)
        parts = translated_joined.split(BATCH_SEP.strip())
        # If split count doesn't match, fallback to per-item
        if len(parts) == len(batch):
            return [p.strip() for p in parts]
        # Fallback: translate individually
        logger.warning("Batch split mismatch (%d vs %d), translating individually.",
                       len(parts), len(batch))
        return [_translate_chunk(t, translator) for t in batch]

    for text in texts:
        text_len = len(text)
        if text_len > MAX_CHUNK:
            # Flush current batch first
            results.extend(flush(batch))
            batch = []
            batch_len = 0
            # Translate oversized text in one call
            results.append(_translate_chunk(text, translator))
            continue

        if batch and batch_len + len(BATCH_SEP) + text_len > BATCH_MAX:
            results.extend(flush(batch))
            batch = []
            batch_len = 0

        batch.append(text)
        batch_len += text_len + len(BATCH_SEP)

    results.extend(flush(batch))
    return results


# ---------------------------------------------------------------------------
# ReportLab styles
# ---------------------------------------------------------------------------

def _build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "PDFBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    )
    title_xl = ParagraphStyle(
        "PDFTitleXL",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        spaceBefore=18,
        spaceAfter=12,
        textColor=colors.HexColor("#1a1a2e"),
    )
    title_md = ParagraphStyle(
        "PDFTitleMD",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceBefore=14,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a2e"),
    )
    title_sm = ParagraphStyle(
        "PDFTitleSM",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        spaceBefore=10,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a2e"),
    )
    footer = ParagraphStyle(
        "PDFFooter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#666666"),
    )
    code = ParagraphStyle(
        "PDFCode",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        leftIndent=12,
        rightIndent=12,
        spaceBefore=6,
        spaceAfter=6,
        backColor=colors.HexColor("#f5f5f5"),
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=0.5,
        borderPadding=6,
    )
    return {"body": body, "title_xl": title_xl, "title_md": title_md, "title_sm": title_sm, "footer": footer, "code": code}


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
      1. Extract text blocks and images per page with PyMuPDF.
      2. Classify each block (code / title / body text).
      3. Batch-translate all non-code blocks together (fewer API calls → fewer rate-limit errors).
      4. Rebuild a brand-new PDF with ReportLab (proper text flow, no overlaps, no blank pages).
    """
    logger.info("Starting translation pipeline: %s", input_path)
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    styles = _build_styles()

    doc_in = fitz.open(input_path)
    total_pages = len(doc_in)

    # ── Pass 1: extract all content blocks ──────────────────────────────────
    # Each entry: ("code"|"title"|"body"|"image", data)
    content_blocks: list[tuple[str, object]] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for page_idx, page in enumerate(doc_in):
            logger.info("Extracting page %d / %d", page_idx + 1, total_pages)
            blocks_norm = page.get_text("blocks")
            blocks_dict = page.get_text("dict")["blocks"]

            merged_blocks = []
            for b_norm, b_dict in zip(blocks_norm, blocks_dict):
                x0, y0, x1, y1, content, block_no, block_type = b_norm
                max_size = 0.0
                font_name = ""
                if block_type == 0:
                    for line in b_dict.get("lines", []):
                        for span in line.get("spans", []):
                            if span["size"] > max_size:
                                max_size = span["size"]
                                font_name = span["font"]
                merged_blocks.append((x0, y0, x1, y1, content, block_no, block_type, max_size, font_name.lower()))

            merged_blocks.sort(key=lambda b: (round(b[1] / 10) * 10, b[0]))

            for block in merged_blocks:
                x0, y0, x1, y1, content, block_no, block_type, max_size, font_name = block

                if block_type == 1:  # image
                    try:
                        rect = fitz.Rect(x0, y0, x1, y1)
                        # Skip very small image clips (likely noise / decorations)
                        if rect.width < 20 or rect.height < 20:
                            continue
                        pix = page.get_pixmap(clip=rect, dpi=150)
                        img_file = tmp_path / f"img_{page_idx}_{block_no}.png"
                        pix.save(str(img_file))
                        available_w = A4[0] - 4 * cm
                        scale = min(available_w / max(pix.width, 1), 1.0)
                        draw_w = pix.width * scale * (72 / 150)
                        draw_h = pix.height * scale * (72 / 150)
                        content_blocks.append(("image", (str(img_file), draw_w, draw_h), {}))
                    except Exception as exc:
                        logger.warning("Image extract failed p%d b%d: %s", page_idx, block_no, exc)
                    continue

                text = _clean_block(content.strip())
                if not text:
                    continue

                is_footer = (y0 > 750 or (y0 > 600 and max_size < 10.0))
                is_header = y0 < 60 and max_size < 10.0

                if is_footer or is_header:
                    logger.debug("Skipping header/footer text on page %d: %s", page_idx, text)
                    continue  # Filter out entirely to prevent random text from showing up

                is_mono = "mono" in font_name or "courier" in font_name or "consolas" in font_name
                is_bold = "bold" in font_name or "semibold" in font_name or "black" in font_name
                is_italic = "italic" in font_name or "oblique" in font_name

                btype = "code" if is_mono else classify(text)

                meta = {
                    "size": round(max_size, 1), 
                    "page": page_idx,
                    "bold": is_bold,
                    "italic": is_italic
                }

                if btype == "body":
                    # Smart split: TOC blocks get one entry per line;
                    # normal prose blocks get lines joined into a paragraph.
                    for sub in _split_block_lines(text):
                        if sub:
                            content_blocks.append(("body", sub, meta))
                elif btype == "code":
                    content_blocks.append(("code", text, meta))
                else:
                    content_blocks.append((btype, text, meta))

            if progress_callback:
                progress_callback(page_idx + 1, total_pages)

        doc_in.close()

        # ── Pass 2: batch-translate all translatable blocks ──────────────────
        logger.info("Translating %d blocks in batches…", len(content_blocks))

        # Collect indices and texts of blocks that need translation
        to_translate_idx: list[int] = []
        to_translate_txt: list[str] = []

        for i, (btype, data, meta) in enumerate(content_blocks):
            if btype in ("title", "body", "footer") and isinstance(data, str):
                to_translate_idx.append(i)
                to_translate_txt.append(data)

        logger.info("Sending %d text blocks to translator…", len(to_translate_txt))
        translated_texts = _translate_batch(to_translate_txt, translator)

        # Write back translations into content_blocks
        for idx, translated in zip(to_translate_idx, translated_texts):
            btype, _, meta = content_blocks[idx]
            content_blocks[idx] = (btype, translated, meta)

        # ── Pass 3: build PDF with ReportLab ─────────────────────────────────
        logger.info("Rendering output PDF…")
        story: list = []
        current_page = 0

        for btype, data, meta in content_blocks:
            page_idx = meta.get("page", current_page)
            if page_idx > current_page:
                story.append(PageBreak())
                current_page = page_idx

            if btype == "image":
                img_file, w, h = data
                story.append(Image(img_file, width=w, height=h))
                story.append(Spacer(1, 4))

            elif btype == "code":
                safe = str(data).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                story.append(Preformatted(safe, styles["code"]))

            else:  # title, body
                safe = str(data).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                font_size = meta.get("size", 10.5)

                if btype == "title" or font_size >= 12.0:
                    if font_size > 20.0:
                        base_style = styles["title_xl"]
                    elif font_size >= 14.0:
                        base_style = styles["title_md"]
                    else:
                        base_style = styles["title_sm"]
                else:
                    base_style = styles["body"]

                if meta.get("bold"):
                    safe = f"<b>{safe}</b>"
                if meta.get("italic"):
                    safe = f"<i>{safe}</i>"

                story.append(Paragraph(safe, base_style))

        doc_out = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm,  bottomMargin=2 * cm,
        )
        doc_out.build(story)

    logger.info("Done → %s", output_path)
