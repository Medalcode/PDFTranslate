import sys
import logging
from app.translator import translate_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

try:
    print("Testing translation on the first few pages (via _sample5.pdf)...")
    input_file = "pruebas/_sample5.pdf"
    output_file = "outputs/sample5_traducido_test.pdf"
    
    translate_pdf(
        input_file,
        output_file,
        source_lang="en",
        target_lang="es",
    )
    print(f"✅ Terminado con éxito: el archivo se ha guardado en {output_file}")
except Exception as e:
    print(f"❌ Ocurrió un error: {e}")
