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
**Capacidades Avanzadas**:
- **Deduplicación Automática**: Consulta `data/translations_cache.db` para omitir bloques ya procesados (ahorro de costo/tiempo).
- **Glosario Forzado**: Respeta términos definidos en `data/glossary.json` para consistencia corporativa.
- **Ajuste Semántico**: Si el texto español desborda el recuadro original, el sistema resume el contenido vía LLM para mantener el layout (Semantic Fit).
**Parámetros**:
- `filepath` (str): Ruta al PDF.
- `target_lang` (str): Código de país (ISO-639-1).
- `preserve_layout` (bool): Mantener coordenadas originales (default: `True`).
- `dry_run` (bool): Prueba de conexión y traducción simple.
- `sample_only` (bool): Traduce solo las primeras N páginas.

## 3. Super-Skill: `generate_test_asset`
**Descripción**: Creación de archivos de prueba dinámicos (PDFs dummy) para QA.
**Parámetros**:
- `output_path` (str): Destino del archivo.
- `scenario` (str): Tipología de asset ('complex_layout', 'simple_text', 'overflow_test').
