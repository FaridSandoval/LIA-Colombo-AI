# Hallazgo: el Teacher's Edition no es indexable con la pipeline actual

**Fecha:** 4 de mayo de 2026
**Autor:** Farid Sandoval (con asistencia Claude)
**Contexto:** Diagnóstico del módulo `scripts/clean_book/` corriendo sobre `data/raw/quarantine/sym2.pdf` (Speak Your Mind 2 Teacher's Edition). El TE era la fuente principal del corpus según el plan original del proyecto.

## TL;DR

El TE no es indexable al RAG con la pipeline actual ni con ajustes menores. Tres problemas compuestos lo bloquean: (1) el PDF fuente tiene corrupción sistemática de caracteres, (2) la nomenclatura de Lessons no coincide con las heurísticas, (3) las Teacher Notes están entrelazadas con el contenido del estudiante sin marcadores estructurales.

**Decisión:** se mantiene el corpus actual (Murphy + Student Book OCR'd + WordList + suplementarios). El TE queda documentado como **trabajo futuro** con justificación técnica.

## Diagnóstico técnico

Ejecutado sobre `data/raw/quarantine/sym2.pdf` con el módulo `scripts/clean_book/` en modo permisivo, primeras 30 páginas y rango completo. Reportes generados en `data/clean_book_test/` y `data/clean_book_audit/`.

### Problema 1 — Corrupción de caracteres en el PDF fuente

**Síntoma:** 333 palabras únicas con doble-letra anómala en Unit 1 (`Myy`, `singger`, `ggroupp`, etc.). El patrón se repite en cada unidad.

**Causa raíz:** la corrupción está en el PDF mismo, no en el extractor. pdfplumber lee correctamente los caracteres tal como el archivo los contiene. Cualquier extractor de texto (pdfplumber, pymupdf, pdfminer) leerá lo mismo porque el problema es del archivo.

**Impacto en el RAG:** el embedding de "singger" no matchea queries por "singer". El retrieval queda degradado para cualquier término afectado, y son cientos por unidad.

**Remediación posible:** re-OCR del PDF con motor moderno sobre las imágenes, o conseguir un PDF original sin esa corrupción.

### Problema 2 — Detección de Lessons nula

**Síntoma:** 0 ocurrencias de `## Lesson` en `fundamental_plus_unit01_extraordinary.md`. El pipeline marca con `<!-- TODO: revisar -->` cada unidad por falta de sub-secciones detectadas.

**Causa raíz:** el TE no usa la nomenclatura "Lesson 1A / 1B" que asume el regex actual (`scripts/clean_book/configs/speak_your_mind_2.yaml`). Usa otra estructura que requiere inspección manual del PDF para identificar.

**Impacto en el RAG:** sin sub-secciones, cada unidad es un blob de ~1000 líneas. El parent-child chunking pierde estructura — los parents se vuelven monolíticos (>10k chars), degradando context_precision.

**Remediación posible:** análisis manual del TE para identificar la nomenclatura real, re-escritura de las heurísticas en el YAML.

### Problema 3 — Teacher Notes sin separar

**Síntoma:** 1 sola ocurrencia de `### Teacher Notes` en 1007 líneas de Unit 1. Las instrucciones para profesor fluyen mezcladas con el texto del estudiante desde la línea 50 en adelante.

**Causa raíz:** el clasificador `_is_teacher_note` actual depende de marcadores textuales explícitos ("Teaching Tip", "Background Note", etc.) y de detección por sidebar width. El TE de SYM2 no parece usar esos marcadores y las notas no están en sidebars sino inline.

**Impacto en el RAG:** el corpus indexaría instrucciones de profesor mezcladas con contenido del estudiante. El LLM puede mezclar respuestas dirigidas al docente con respuestas al alumno (ej. "Pídale al estudiante que…" en una respuesta directa al estudiante).

**Remediación posible:** re-pensar el clasificador con un enfoque distinto (probablemente requiere ML o regex muy específicos del estilo del libro).

### Problema 4 (secundario) — Unit 12 absorbe el remanente

**Síntoma:** Unit 12 tiene 8208 líneas (246 KB) vs ~1000 líneas (~30-38 KB) en las otras 11 unidades.

**Causa raíz:** el detector de fronteras de unidad pierde el final del libro y mete apéndices, answer keys y material adicional dentro del archivo de Unit 12.

**Remediación posible:** agregar detección de "fin de cuerpo principal" para no extender Unit 12 hasta el final del PDF.

## Estimación de esfuerzo para hacerlo viable

| Trabajo | Esfuerzo |
|---|---|
| Re-OCR del PDF (con verificación) | 1-2h |
| Inspección manual del TE para identificar nomenclatura de Lessons | 2-3h |
| Re-escritura de heurísticas de Lessons + iteración | 3-4h |
| Re-pensar clasificador de Teacher Notes (puede requerir ML) | 4-6h |
| Validación + iteración | 4-6h |
| Re-indexar y re-correr benchmark para comparar contra Murphy | 2h |
| **Total** | **16-23 horas** |

Con incertidumbre alta — la remediación del Problema 1 (re-OCR) puede requerir múltiples intentos.

## Decisión y justificación

Dada la asesoría con Ferro el jueves 7 de mayo (3 días útiles), y los pendientes simultáneos (resumen ejecutivo, corrida grande con baseline, validación con usuarios), se decide **no atacar el TE en esta semana**.

El corpus actual (Murphy + Student Book OCR'd + WordList + suplementarios) ya demostró cobertura útil sobre GRAMMAR (faithfulness=0.40, answer_relevancy=0.74) y guardrails (3/3 OFF_DOMAIN correctos). Es una base defendible para la sustentación.

## Implicaciones para el documento académico

1. La sección de stack técnico debe reflejar el corpus real, no el plan original.
2. La justificación de Murphy como referencia gramatical debe ser explícita (libro estándar global, PDF nativo limpio, cobertura A1-B2, validación pedagógica de décadas).
3. El TE entra en la sección de "Trabajos futuros" con esta nota técnica como respaldo.

## Datos de respaldo

- Output de auditoría: `data/clean_book_audit/audit_report.json`
- Output de pipeline test: `data/clean_book_test/fundamental_plus_unit*.md` (12 archivos)
- PDF fuente: `data/raw/quarantine/sym2.pdf`
- Módulo de pipeline: `scripts/clean_book/`
