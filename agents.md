# Documentación de Agentes (agents.md)

## 1. Agente Generalista (Procesamiento de Documentos)
**Descripción**: Un agente altamente versátil que consolida las tareas anteriormente separadas (y redundantes) de análisis, inspección y validación de texto en archivos PDF.
**Responsabilidades**:
- Extraer texto y metadatos de documentos PDF.
- Inspeccionar cajas de texto (bounding boxes), layouts y estructura visual.
- Validar y clasificar el contenido textual según se requiera.
**Skills asociadas**: `analyze_pdf`

## 2. Agente Traductor
**Descripción**: Agente encargado de la capa de traducción del texto, especializado en mantener la estructura semántica original.
**Responsabilidades**:
- Orquestar la traducción entre múltiples idiomas usando motores NLP pertinentes.
- Restablecer la localización de cajas de texto (si se solicita).
**Skills asociadas**: `translate_document`
