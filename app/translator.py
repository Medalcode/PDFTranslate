"""
PDFTranslate — Core Translation Engine v2
==========================================

Architecture change from v1:
  ❌ v1: Extract → Translate → Rebuild with ReportLab (loses layout)
  ✅ v2: Extract → Translate → OVERLAY on original PDF (preserves layout)

Pipeline:
  1. Pass 1 — Extract all text blocks with bounding boxes (PyMuPDF)
  2. Pass 2 — Batch-translate with LLM (structured prompt) or Google Translate fallback
  3. Pass 3 — Overlay: redact original text, insert translated text at same position

LLM providers supported (via .env):
  - gemini  → google-generativeai (recommended)
  - openai  → openai SDK
  - custom  → any OpenAI-compatible endpoint (Together AI, Ollama, etc.)
  - (none)  → falls back to deep-translator / Google Translate
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import fitz  # PyMuPDF

from app.config import SOURCE_LANG, TARGET_LANG
from app.text_classifier import classify

logger = logging.getLogger(__name__)


# ── Prompts ───────────────────────────────────────────────────────────────────

_TRANSLATION_PROMPT = """\
You are a professional technical translator specialized in preserving document structure.

Translate the following numbered text blocks from English to Spanish.

STRICT RULES:
1. Return EXACTLY the same number of numbered blocks in [N] format.
2. DO NOT merge, split, or reorder blocks.
3. Preserve line breaks and bullet points within each block.
4. DO NOT translate: source code, commands, file paths, URLs, or variable names.
5. Proper nouns, product names, and acronyms stay unchanged.
6. If a block should not be translated, return it as-is.
7. Output ONLY the translated blocks — no commentary.

BLOCKS:
{blocks}

TRANSLATION:"""

_LENGTH_ADJUST_PROMPT = """\
The Spanish text below must fit in roughly {target_len} characters.
Shorten it while preserving ALL key information. Be concise and natural.
Return the shortened text only — no commentary.

TEXT:
{text}"""


# ── Protected technical terms ─────────────────────────────────────────────────

_PROTECTED_TERMS = {
    # Apache ecosystem
    "Hadoop", "HDFS", "YARN", "MapReduce", "Spark", "Hive", "Pig",
    "Flume", "Sqoop", "HBase", "ZooKeeper", "Avro", "Parquet",
    "Oozie", "Tez", "Kafka", "Storm", "Flink", "Cassandra", "MongoDB",
    "Thrift", "Crunch", "Nutch",
    # Cloud / infra
    "AWS", "S3", "EC2", "GCS", "Azure", "Docker", "Kubernetes",
    # Languages / tools
    "Java", "Python", "Scala", "Ruby", "Maven", "Gradle", "Git",
    "MRUnit", "Kerberos", "WebHDFS", "HttpFS",
    # Formats / protocols
    "JSON", "XML", "CSV", "HTTP", "REST", "JDBC", "ODBC", "SQL",
    "ISBN", "API", "IDE", "GFS", "DAG", "UDF", "UDAF", "IDL",
    # Social / branding
    "Twitter", "Facebook", "YouTube", "LinkedIn", "GitHub", "Safari",
    "O'Reilly", "Cloudera", "Apache", "Peachpit", "Syngress",
    # Misc
    "US", "UK", "CAN",
}

_PH_PREFIX = "PROT"
_PROTECTED_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _PROTECTED_TERMS) + r")\b"
)


def _protect(text: str) -> tuple[str, dict[str, str]]:
    ph_map: dict[str, str] = {}
    idx = 0
    for m in _PROTECTED_RE.finditer(text):
        term = m.group(0)
        if term not in ph_map.values():
            ph = f"{_PH_PREFIX}{idx:03d}X"
            ph_map[ph] = term
            idx += 1
    for ph, term in ph_map.items():
        text = re.sub(r"\b" + re.escape(term) + r"\b", ph, text)
    return text, ph_map


def _restore(text: str, ph_map: dict[str, str]) -> str:
    for ph, term in ph_map.items():
        text = text.replace(ph, term)
    return text


# ── Text cleaning ─────────────────────────────────────────────────────────────

_SOFT_HYPHEN  = re.compile(r"\xad")
_HYPHEN_BREAK = re.compile(r"-(\n)\s*")
_BULLET_GLYPH = re.compile(r"[\u25a0\u25cf\u2022\u2023]")


def _clean_text(text: str) -> str:
    text = _SOFT_HYPHEN.sub("", text)
    text = _HYPHEN_BREAK.sub("", text)
    text = _BULLET_GLYPH.sub("• ", text)
    return text.strip()


# ── LLM backends ──────────────────────────────────────────────────────────────

class _LLMBase:
    def call(self, prompt: str) -> str:
        raise NotImplementedError


class _GeminiBackend(_LLMBase):
    def __init__(self, api_key: str, model: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(model or "gemini-2.0-flash")

    def call(self, prompt: str) -> str:
        try:
            r = self._model.generate_content(prompt)
            return r.text or ""
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            return f"Error: {exc}"


class _OpenAIBackend(_LLMBase):
    def __init__(self, api_key: str, model: str, base_url: str):
        from openai import OpenAI
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)
        self._model = model or "gpt-4o-mini"

    def call(self, prompt: str) -> str:
        try:
            r = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return r.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            return f"Error: {exc}"


def _build_llm(provider: str, api_key: str, model: str, base_url: str) -> Optional[_LLMBase]:
    if not api_key:
        return None
    try:
        if provider == "gemini":
            return _GeminiBackend(api_key, model)
        if provider in ("openai", "custom", "together"):
            return _OpenAIBackend(api_key, model, base_url)
    except ImportError as exc:
        logger.warning("LLM SDK not installed for '%s': %s", provider, exc)
    except Exception as exc:
        logger.warning("LLM backend init failed: %s", exc)
    return None


# ── LLM translation ───────────────────────────────────────────────────────────

_LLM_BATCH = 20          # blocks per LLM call
_LLM_DELAY = 0.5         # courtesy delay between calls


def _parse_numbered_blocks(response: str, expected: int) -> Optional[list[str]]:
    """Parse [N] block format from LLM response."""
    pattern = re.compile(r"\[(\d+)\]\s*(.*?)(?=\[\d+\]|\Z)", re.DOTALL)
    matches = pattern.findall(response)
    if not matches:
        return None
    parsed: dict[int, str] = {int(n): t.strip() for n, t in matches}
    result = [parsed.get(i, "") for i in range(1, expected + 1)]
    # Reject if more than 40% of blocks are empty
    if sum(1 for r in result if r) < expected * 0.6:
        return None
    return result


class LLMQuotaExceeded(Exception):
    pass


def _translate_with_llm(texts: list[str], llm: _LLMBase) -> list[str]:
    """Translate a list of blocks using LLM numbered-block batching."""
    results = list(texts)  # default: unchanged
    consecutive_failures = 0

    for start in range(0, len(texts), _LLM_BATCH):
        batch = texts[start : start + _LLM_BATCH]
        # Protect terms before sending
        protected_batch, ph_maps = [], []
        for t in batch:
            p, ph = _protect(t)
            protected_batch.append(p)
            ph_maps.append(ph)

        numbered = "\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(protected_batch))
        prompt = _TRANSLATION_PROMPT.format(blocks=numbered)

        success = False
        for attempt in range(4):  # Reduced to 4 attempts to avoid huge hangs
            try:
                time.sleep(_LLM_DELAY)
                response = llm.call(prompt)
                
                if "429" in response or "quota" in response.lower() or "rate limit" in response.lower():
                    raise ValueError(f"Rate Limit/Quota: {response}")
                    
                parsed = _parse_numbered_blocks(response, len(batch))
                if parsed:
                    for j, (translated, ph_map) in enumerate(zip(parsed, ph_maps)):
                        # Restore protected terms, use original if translation blank
                        t = _restore(translated, ph_map) if translated else batch[j]
                        results[start + j] = t
                    success = True
                    consecutive_failures = 0
                    break
                logger.warning("LLM block parse failed (attempt %d), retrying…", attempt + 1)
            except Exception as exc:
                wait = 5 + (2 ** attempt)  # Start at 6s wait, scale slowly
                logger.warning("LLM call error attempt %d: %s. Wait %ds…", attempt + 1, exc, wait)
                time.sleep(wait)

        if not success:
            logger.error("LLM batch %d failed after all retries.", start)
            consecutive_failures += 1
            if consecutive_failures >= 3:
                logger.error("Too many consecutive LLM failures. Aborting LLM translation.")
                raise LLMQuotaExceeded("Consecutive LLM failures exceeded limit")

    return results


# ── Google Translate fallback ─────────────────────────────────────────────────

_GT_DELAY    = 1.2
_GT_BATCH_SEP = " 🔹 "
_GT_BATCH_MAX = 3000


def _translate_with_google(texts: list[str], source: str, target: str) -> list[str]:
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source=source, target=target)
    final: dict[int, str] = {}

    def _call(t: str) -> str:
        for attempt in range(4):
            try:
                time.sleep(_GT_DELAY)
                return translator.translate(t) or t
            except Exception as exc:
                time.sleep(2 ** attempt)
                logger.warning("GT retry %d: %s", attempt + 1, exc)
        return t

    def flush(batch: list[str], idxs: list[int]) -> None:
        if not batch:
            return
        joined = _GT_BATCH_SEP.join(batch)
        p_joined, ph_map = _protect(joined)
        translated_joined = _call(p_joined)
        translated_joined = _restore(translated_joined, ph_map)
        parts = translated_joined.split(_GT_BATCH_SEP.strip())
        if len(parts) == len(batch):
            for idx, t in zip(idxs, parts):
                final[idx] = t.strip()
            return
        # Fallback: per-item
        logger.warning("GT batch split mismatch — translating individually.")
        for idx, t in zip(idxs, batch):
            p_t, ph = _protect(t)
            final[idx] = _restore(_call(p_t), ph)

    batch: list[str] = []
    idxs:  list[int] = []
    batch_len = 0

    for i, text in enumerate(texts):
        if len(text) > 4500:
            flush(batch, idxs)
            batch, idxs, batch_len = [], [], 0
            p_t, ph = _protect(text)
            final[i] = _restore(_call(p_t), ph)
            continue
        if batch and batch_len + len(_GT_BATCH_SEP) + len(text) > _GT_BATCH_MAX:
            flush(batch, idxs)
            batch, idxs, batch_len = [], [], 0
        batch.append(text)
        idxs.append(i)
        batch_len += len(text) + len(_GT_BATCH_SEP)

    flush(batch, idxs)
    return [final.get(i, texts[i]) for i in range(len(texts))]


# ── PDF font mapping ──────────────────────────────────────────────────────────

def _pdf_fontname(font_name: str, bold: bool, italic: bool) -> str:
    """Map a PDF font name to a PyMuPDF base-14 font identifier."""
    fn = font_name.lower()
    is_mono  = "mono" in fn or "courier" in fn or "consolas" in fn or "code" in fn
    is_times = "times" in fn or "serif" in fn

    if is_mono:
        if bold and italic: return "cobi"
        if bold:            return "cobo"
        if italic:          return "coit"
        return "cour"
    if is_times:
        if bold and italic: return "tibi"
        if bold:            return "tibo"
        if italic:          return "tiit"
        return "tiro"
    # Default: Helvetica
    if bold and italic: return "hebi"
    if bold:            return "hebo"
    if italic:          return "heit"
    return "helv"


# ── Overlay helpers ───────────────────────────────────────────────────────────

_MIN_FONT = 6.0


def _insert_autofit(
    page:      fitz.Page,
    rect:      fitz.Rect,
    text:      str,
    font_size: float,
    font_name: str,
    bold:      bool,
    italic:    bool,
    color:     tuple,
) -> None:
    """Insert text into rect, shrinking font until it fits."""
    fname = _pdf_fontname(font_name, bold, italic)
    fs = max(font_size, 7.0)  # don't start below 7pt

    while fs >= _MIN_FONT:
        rc = page.insert_textbox(
            rect, text,
            fontname=fname,
            fontsize=fs,
            color=color,
            align=0,   # left
        )
        if rc >= 0:
            return
        fs -= 0.5

    # Last resort at minimum size — let PyMuPDF truncate
    page.insert_textbox(rect, text, fontname=fname, fontsize=_MIN_FONT, color=color)


# ── Main entry point ──────────────────────────────────────────────────────────

def translate_pdf(
    input_path: str,
    output_path: str,
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
    progress_callback=None,
) -> None:
    """
    Translate a PDF document using the v2 overlay pipeline.

    Key difference from v1:
      - Images, borders, and decorations remain untouched (they're not text).
      - Text is redacted in-place and replaced with the translation at the
        exact same bounding box — no ReportLab reconstruction needed.
    """
    from app.config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

    logger.info("PDFTranslate v2 | input: %s", input_path)

    # Setup translation backend
    llm = _build_llm(LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL)
    if llm:
        logger.info("LLM backend: %s (%s)", LLM_PROVIDER, LLM_MODEL or "default model")
    else:
        logger.info("No LLM configured — using Google Translate fallback")

    doc = fitz.open(input_path)
    total_pages = len(doc)

    # ── Pass 1: Extract all text blocks ──────────────────────────────────────
    all_blocks: list[dict] = []

    for page_idx, page in enumerate(doc):
        logger.info("Extracting page %d / %d", page_idx + 1, total_pages)
        raw = page.get_text("dict")

        for block in raw["blocks"]:
            if block["type"] == 1:           # image block — keep as-is
                continue

            # Aggregate text and font metadata across all spans
            full_text = ""
            max_size  = 0.0
            font_name = ""
            is_bold   = False
            is_italic = False
            is_mono   = False
            color     = (0, 0, 0)

            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    full_text += span.get("text", "")
                    sz = span.get("size", 0)
                    fn = span.get("font", "").lower()
                    if sz > max_size:
                        max_size  = sz
                        font_name = fn
                    if any(k in fn for k in ("bold", "black", "semibold", "heavy")):
                        is_bold = True
                    if any(k in fn for k in ("italic", "oblique")):
                        is_italic = True
                    if any(k in fn for k in ("mono", "courier", "consolas", "code")):
                        is_mono = True
                    # Decode span color (packed int → RGB float tuple)
                    c = span.get("color", 0)
                    if isinstance(c, int):
                        color = (
                            ((c >> 16) & 0xFF) / 255,
                            ((c >> 8)  & 0xFF) / 255,
                            ( c        & 0xFF) / 255,
                        )
                full_text += "\n"

            text = _clean_text(full_text)
            if not text:
                continue

            rect = fitz.Rect(block["bbox"])

            # Filter out running headers and footers
            is_header = rect.y0 < 55 and max_size < 10.0
            is_footer = rect.y0 > 750 or (rect.y0 > 600 and max_size < 10.0)
            if is_header or is_footer:
                logger.debug("Skipping header/footer on page %d: %r", page_idx, text[:60])
                continue

            # Classify block type
            btype = "code" if is_mono else classify(text)

            all_blocks.append({
                "page":      page_idx,
                "rect":      rect,
                "text":      text,
                "type":      btype,
                "font_size": max(max_size, 7.0),
                "font_name": font_name,
                "bold":      is_bold,
                "italic":    is_italic,
                "color":     color,
            })

        if progress_callback:
            progress_callback(page_idx + 1, total_pages)

    # ── Pass 2: Translate all translatable blocks ─────────────────────────────
    translatable_idx = [
        i for i, b in enumerate(all_blocks)
        if b["type"] in ("body", "title")
    ]
    texts_to_translate = [all_blocks[i]["text"] for i in translatable_idx]

    logger.info("Translating %d blocks (%d total extracted)…",
                len(texts_to_translate), len(all_blocks))

    if texts_to_translate:
        if llm:
            try:
                translated = _translate_with_llm(texts_to_translate, llm)
            except LLMQuotaExceeded as exc:
                logger.error("LLM aborted (%s). Switching to Google Translate fallback...", exc)
                translated = _translate_with_google(texts_to_translate, source_lang, target_lang)
            except Exception as exc:
                logger.error("LLM unexpected error: %s. Switching to Google Translate fallback...", exc)
                translated = _translate_with_google(texts_to_translate, source_lang, target_lang)
        else:
            translated = _translate_with_google(texts_to_translate, source_lang, target_lang)

        for i, t in zip(translatable_idx, translated):
            all_blocks[i]["translated"] = t

    # Non-translatable blocks keep their original text (code, etc.)
    for b in all_blocks:
        b.setdefault("translated", b["text"])

    # ── Pass 3: Overlay — redact originals, insert translations ──────────────
    logger.info("Applying overlay to %d pages…", total_pages)

    for page_idx, page in enumerate(doc):
        page_blocks = [b for b in all_blocks if b["page"] == page_idx]
        if not page_blocks:
            continue

        # Step 3a — Mark all text regions for redaction (white fill)
        for b in page_blocks:
            page.add_redact_annot(b["rect"], fill=(1, 1, 1))
        page.apply_redactions()

        # Step 3b — Insert translated text at the same position
        for b in page_blocks:
            _insert_autofit(
                page      = page,
                rect      = b["rect"],
                text      = b["translated"],
                font_size = b["font_size"],
                font_name = b["font_name"],
                bold      = b["bold"],
                italic    = b["italic"],
                color     = b["color"],
            )

    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    logger.info("Done → %s", output_path)
