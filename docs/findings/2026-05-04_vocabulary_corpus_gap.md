# Hallazgo: brecha entre golden set VOCABULARY y corpus indexado

**Fecha:** 4 de mayo de 2026
**Autor:** Farid Sandoval
**Contexto:** Benchmark RAGAS sobre categorías VOCABULARY (5 ítems) y GUARDRAIL_OFF_DOMAIN (3 ítems) usando gemma2:9b como LLM y gpt-4o-mini como juez.

## TL;DR

El RAG está funcionando correctamente. El problema está en el **golden set**: 5/5 ítems de VOCABULARY evalúan términos que el corpus indexado nunca prometió cubrir. Las métricas RAGAS bajas (`faithfulness=0.0`, `context_recall=0.0`) son consecuencia directa de esto, no un defecto del retrieval ni del modelo.

## Métricas observadas

| Métrica | Valor sobre 8 ítems (5 VOCAB + 3 OFF) |
|---|---|
| faithfulness | 0.00 |
| answer_relevancy | 0.79 |
| context_precision | 0.17 |
| context_recall | 0.00 |
| guardrail_activations | low_confidence: 2, off_domain: 3 |
| hallucination_violations | 1 |

## Diagnóstico

### Lo que funcionó

- **GUARDRAIL_OFF_DOMAIN: 3/3 ítems disparan correctamente.** OFF01 (capital de Francia), OFF02 (Python for loop), OFF03 (cédula) fueron rechazados con redirección al curso.
- **Guardrail low_confidence: 2/5 ítems VOCAB disparan correctamente.** V01 (cuñado) y V03 (assist) — el sistema reconoció que no tenía información y se rehusó a responder en lugar de alucinar.

### Lo que falló (y por qué)

Los 3 ítems VOCAB que SÍ generaron respuesta (V02 supper/dinner, V04 give up, V05 weather) lo hicieron usando **conocimiento paramétrico del LLM**, no el contexto recuperado. RAGAS detectó esto correctamente y reportó `faithfulness=0`.

Inspección directa del vectorstore Chroma (sin LLM) confirma:

1. **Los términos del golden set NO están en el corpus.** Búsqueda case-insensitive en `SYM_2_WordList.xlsx` de los 8 términos evaluados (`brother-in-law`, `cuñado`, `assist`, `supper`, `dinner`, `give up`, `sunny`, `cloudy`) no encontró entradas dedicadas. Solo "dinner" aparece como mención incidental en ejemplos de otras palabras.

2. **No existe `source_type=vocabulary` en el vectorstore.** La WordList se indexó como `source_type=syllabus` (600 chunks), pero contiene los headwords curriculares del SYM_2, no un diccionario temático.

3. **El retrieval cae a Murphy.** En 7 búsquedas de prueba sobre términos VOCAB del golden set, ~60% de los chunks devueltos provenían de `grammar_reference` (Murphy's English Grammar in Use). El único caso donde el retrieval acertó fue V04 (`give up`) porque Murphy's Unit 143 cubre phrasal verbs.

4. **El `expected_sources` del golden set apunta a fuentes que no existen.** Valores como `"family"`, `"false friend"`, `"weather"`, `"phrasal verb"` no corresponden a ningún documento ni `source_type` indexado.

### Conexión con la auditoría previa

Este hallazgo confirma los issues **GS3** y **GS4** documentados en `auditoria_completa_LIA.md` (26 abril):
- GS3: `must_mention` con keywords genéricos.
- GS4: `expected_sources` con substrings poco discriminativos.

## Opciones de acción

**Opción A — Reorientar VOCABULARY al syllabus real**
Reescribir los 5 ítems usando headwords que efectivamente están en `SYM_2_WordList.xlsx`. Ejemplo: en vez de "¿Cómo se dice 'cuñado' en inglés?", preguntar por términos del Unit 1 (Role Models) o Unit 2 (Party).
- Costo: ninguno adicional.
- Trade-off: el golden set queda alineado al corpus, pero pierde valor como prueba de "vocabulario conversacional realista".

**Opción B — Agregar un diccionario temático al corpus**
Indexar un recurso adicional con definiciones de vocabulario temático (familia, false friends, weather, comidas).
- Esfuerzo: 4-8 horas (buscar fuente apropiada, validar derechos, indexar).
- Costo: tiempo + decisión sobre qué fuente.
- Trade-off: el golden set queda como está, pero el corpus crece y hay que justificar la nueva fuente académicamente.

**Opción C — Combinación**
Reorientar 3/5 ítems a headwords del syllabus (rápido), y dejar 2/5 como "VOCABULARY out-of-corpus" para evaluar específicamente el comportamiento del guardrail low_confidence.
- Esfuerzo: 2 horas.
- Trade-off: golden set más pequeño pero más honesto sobre lo que el sistema cubre.

## Anexo — datos de respaldo

- CSV detallado: `eval/results/detail_gemma2_9b.csv` (run del 4 mayo 2026)
- CSV agregado: `eval/results/llm_benchmark.csv` (última fila: n_items=8)
