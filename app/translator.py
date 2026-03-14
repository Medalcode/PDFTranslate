import os
import logging
from pathlib import Path
import tempfile
import uuid

import fitz  # PyMuPDF
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

# Max chars GoogleTranslator can handle per request
MAX_CHUNK = 4900

import time

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

def _translate_text(text: str, translator: GoogleTranslator, max_retries: int = 3) -> str:
    """Translate text, handling long blocks and rate limits by retrying."""
    stripped = text.strip()
    if not stripped:
        return text

    def do_translate(chunk, retries=0):
        while retries < max_retries:
            try:
                time.sleep(0.5)
                res = translator.translate(chunk)
                return res if res else chunk
            except Exception as e:
                logger.warning(f"Translation error (retry {retries+1}/{max_retries}): {e}")
                retries += 1
                time.sleep(2 * retries)
        logger.error(f"Failed to translate chunk after {max_retries} retries.")
        return chunk

    if len(stripped) <= MAX_CHUNK:
        return do_translate(stripped)

    chunks = _split_text(stripped)
    translated_chunks = [do_translate(c) for c in chunks]
    return " ".join(translated_chunks)


def translate_pdf(
    input_path: str,
    output_path: str,
    source_lang: str = SOURCE_LANG,
    target_lang: str = TARGET_LANG,
    progress_callback=None,
) -> None:
    """
    Translates a PDF by completely extracting its flow into HTML, translating it,
    and rendering a brand new PDF via xhtml2pdf.
    """
    logger.info("Starting new HTML-based translation pipeline...")
    translator = GoogleTranslator(source=source_lang, target=target_lang)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        html_content = [
            '<!DOCTYPE html>',
            '<html><head><meta charset="UTF-8">',
            '<style>',
            '@page { size: a4; margin: 2cm; }',
            'body { font-family: Helvetica, sans-serif; line-height: 1.5; color: #333; }',
            'p { margin-bottom: 10pt; text-align: justify; }',
            'h1, h2, h3 { margin-top: 15pt; margin-bottom: 5pt; color: #111; }',
            'pre { background-color: #f4f4f4; padding: 10pt; font-family: Courier, monospace; font-size: 9pt; }',
            'img { max-width: 100%; height: auto; margin: 10pt 0; }',
            '</style>',
            '</head><body>'
        ]

        doc = fitz.open(input_path)
        total_pages = len(doc)
        
        for page_index, page in enumerate(doc):
            logger.info("Extracting page %d / %d", page_index + 1, total_pages)
            blocks = page.get_text("blocks")
            blocks.sort(key=lambda b: (b[1], b[0]))

            for block in blocks:
                x0, y0, x1, y1, text, block_no, block_type = block
                
                if block_type == 1:
                    try:
                        rect = fitz.Rect(x0, y0, x1, y1)
                        pix = page.get_pixmap(clip=rect)
                        img_filename = f"image_{page_index}_{block_no}.png"
                        img_path = temp_dir_path / img_filename
                        pix.save(str(img_path))
                        html_content.append(f'<img src="{img_path.absolute().as_uri()}"/>')
                    except Exception as e:
                        logger.warning(f"Could not extract image: {e}")
                    continue
                
                clean_text = text.strip()
                if not clean_text: continue

                b_type = classify(clean_text)
                escaped_text = clean_text.replace("<", "&lt;").replace(">", "&gt;")
                
                if b_type == "code":
                    html_content.append(f'<pre><code>{escaped_text}</code></pre>')
                elif b_type == "title":
                    html_content.append(f'<h2 class="translate">{escaped_text}</h2>')
                else:
                    joined_text = " ".join(escaped_text.splitlines())
                    html_content.append(f'<p class="translate">{joined_text}</p>')
            
            if progress_callback:
                progress_callback(page_index + 1, total_pages * 2)
            
        doc.close()
        html_content.append('</body></html>')
        full_html = "\n".join(html_content)

        logger.info("Translating structured HTML content...")
        soup = BeautifulSoup(full_html, "html.parser")
        translatable_nodes = soup.find_all(class_="translate")
        total_nodes = len(translatable_nodes)
        
        for i, node in enumerate(translatable_nodes):
            text = node.get_text(strip=True)
            if text:
                node.string = _translate_text(text, translator)
            if progress_callback and i % 5 == 0:
                current_prog = total_pages + int((i / max(1, total_nodes)) * total_pages)
                progress_callback(current_prog, total_pages * 2)
                
        logger.info("Rendering translated document to PDF...")
        with open(output_path, "wb") as f:
            pisa.CreatePDF(str(soup), dest=f)
        
        logger.info(f"Saved translated PDF to {output_path}")


        if progress_callback:
             progress_callback(total_pages * 2, total_pages * 2)
