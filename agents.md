# Documentación de Agentes (agents.md)

## 1. Agente de Procesamiento de Documentos (Generalista + Traductor)
**Descripción**: Agente integral diseñado para gestionar el ciclo de vida completo de documentos PDF. Consolida las funciones de análisis, inspección técnica, validación de contenido y orquestación de traducción multi-idioma.
**Responsabilidades**:
- Extraer texto, metadatos y layouts de archivos PDF con granularidad variable.
- Clasificar y validar bloques de contenido (encabezados, pies de página, código, tablas).
- Orquestar la traducción usando motores LLM y restaurar la localización visual original (layout preservation).
- Ejecutar pruebas de conectividad y generación de assets sintéticos para QA.
**Skills asociadas**: `analyze_pdf`, `translate_document`, `generate_test_asset`
