import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

import fitz
import os
import sys
from app.translator import translate_pdf

def test_first_30_pages(input_pdf_path, output_pdf_path):
    print(f"Opening original PDF: {input_pdf_path}")
    if not os.path.exists(input_pdf_path):
        print("File not found.")
        sys.exit(1)
        
    print("Extracting first 30 pages...")
    short_pdf_path = input_pdf_path.replace(".pdf", "_first30_html.pdf")
    doc = fitz.open(input_pdf_path)
    doc_short = fitz.open()
    doc_short.insert_pdf(doc, to_page=29) # 0-indexed, so 29 is the 30th page
    doc_short.save(short_pdf_path)
    doc_short.close()
    doc.close()

    print(f"Running HTML pipeline translation on: {short_pdf_path} -> {output_pdf_path}")
    try:
        translate_pdf(short_pdf_path, output_pdf_path, source_lang="en", target_lang="es")
        print(f"Translation successful! Output saved to: {output_pdf_path}")
    except Exception as e:
        print(f"Translation failed: {e}")

if __name__ == "__main__":
    input_pdf = r"D:\Github\PDFTranslate\pruebas\Hadoop - the Definitive Guide.pdf"
    output_pdf = r"D:\Github\PDFTranslate\pruebas\Hadoop_html_30.pdf"
    test_first_30_pages(input_pdf, output_pdf)
