# Documentación de Skills (skills.md)

## 1. Super-Skill: `analyze_pdf`
**Descripción**: Función paramétrica que agrupa en un solo bloque el 80% de la lógica común (apertura de PDF, iteración de páginas, lectura de textboxes). Reemplaza todos los scripts aislados de inspección.
**Parámetros**:
- `filepath` (str): Ruta absoluta al archivo PDF.
- `extract_mode` (enum: 'text_only', 'bounding_boxes', 'styles_and_meta'): Nivel de detalle. 'styles_and_meta' reemplaza a scripts de inspección manual (como `check_cover.py`).
- `check_formatting` (bool): Activa la verificación de jerarquías de texto.
- `output_format` (enum: 'json', 'txt', 'console'): Destino del análisis.

## 2. Super-Skill: `translate_document`
**Descripción**: Centraliza el pipeline de traducción (layout + texto).
**Parámetros**:
- `filepath` (str): Ruta al PDF.
- `target_lang` (str): Código de país (ISO-639-1).
- `preserve_layout` (bool): Mantener coordenadas originales (default: `True`).
- `dry_run` (bool): Realiza una prueba de conexión y traducción de un bloque simple (reemplaza `test_llm.py` y `test_keys.py`).
- `sample_only` (bool): Traduce solo las primeras N páginas para validación (reemplaza `translate_sample.py`).

## 3. Super-Skill: `generate_test_asset`
**Descripción**: Consolida la creación de archivos de prueba dinámicos (PDFs dummy) en una única macro-skill parametrizada.
**Parámetros**:
- `output_path` (str): Destino del archivo.
- `scenario` (str): Tipología de asset (ej: 'complex_layout', 'simple_text').
