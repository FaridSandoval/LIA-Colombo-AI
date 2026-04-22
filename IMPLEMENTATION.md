# LIA-Colombo AI — Guía de Implementación v0.2

Este documento describe el nuevo pipeline RAG avanzado y cómo ponerlo a correr.

## Arquitectura implementada

```
Pregunta
  → [Guardrail de dominio]  (heurística + LLM juez)
  → [Query rewriting / HyDE]  (ES + EN + respuesta hipotética)
  → [Hybrid retrieval]  BM25 + BGE-M3 dense → RRF
  → [Re-ranker]  bge-reranker-v2-m3 → top-5
  → [Parent lookup]  child chunks ↦ parent chunks (small-to-big)
  → [Guardrail baja confianza]
  → [System prompt estructurado + few-shot + contexto]
  → [LLM]  Gemma 2 9B / Llama 3.1 8B / Qwen 3.5 9B (seleccionable)
  → [Respuesta + citaciones]
  → [Trace en LangFuse]
  → [Historial persistente + feedback 👍/👎]
```

## Setup

### 1. Dependencias

```bash
uv sync
```

### 2. Ollama — pull de modelos

```bash
# LLM principal (uno de los tres candidatos del benchmark)
ollama pull gemma2:9b-instruct-q4_K_M
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull qwen3.5:9b

# LLM utilitario (guardrails, rewriting, contextual retrieval)
ollama pull qwen2.5:3b-instruct-q4_K_M
```

### 3. Embeddings y re-ranker (HuggingFace, se bajan al primer uso)

No requieren acción manual — `sentence-transformers` los cachea en `~/.cache/huggingface/`.
Si prefieres pre-bajarlos:

```bash
huggingface-cli download BAAI/bge-m3
huggingface-cli download BAAI/bge-reranker-v2-m3
```

### 4. LangFuse (opcional pero recomendado)

```bash
docker compose up -d
```

Abre `http://localhost:3000`, crea admin, crea proyecto, copia API keys a `.env`:

```bash
cp .env.example .env
# editar LANGFUSE_PUBLIC_KEY y LANGFUSE_SECRET_KEY
```

### 5. Indexar el contenido pedagógico

1. Coloca los materiales (PDF, TXT, MD, XLSX) en `data/raw/`.
2. Coloca `estudiantes_dummies.xlsx` en `data/user/`.
3. Arranca la app:
   ```bash
   uv run streamlit run app.py
   ```
4. Entra como **Admin** y haz clic en **"🔄 Re-indexar Base de Conocimiento"**.
   Esto construye parent + child chunks, los contextualiza con el LLM utilitario,
   los embedea con BGE-M3 y los persiste en Chroma.

> ⚠️ Si cambias el modelo de embeddings, borra `data/chroma_db/` y re-indexa
> (o cambia `CHROMA_COLLECTION_NAME` en `.env` para mantener colecciones en paralelo).

## Uso del app

- **Estudiante** entra con su ID Number → el chat usa el LLM elegido, filtra contexto
  por nivel/unidad inferidos del perfil, muestra citaciones.
- **Admin** puede re-indexar y alternar el LLM activo en vivo.
- El historial se persiste en SQLite (`data/sessions/sessions.db`) por student_id.
- Cada respuesta lleva botones 👍/👎 que se loguean en la tabla `feedback`.

## Benchmark de LLMs (Fase 2)

```bash
# Un modelo específico
python -m eval.run_ragas --llm gemma2:9b-instruct-q4_K_M

# Los tres candidatos
python -m eval.run_ragas --all
```

Resultados:
- `eval/results/detail_<modelo>.csv` → respuestas item por item.
- `eval/results/llm_benchmark.csv` → fila-resumen por ejecución (faithfulness,
  answer_relevancy, context_precision, context_recall, latencia, guardrails).

Editar `LLM_MODEL_NAME` en `.env` con el ganador.

## Validar el golden set (crítico antes de confiar en el benchmark)

El archivo [eval/golden_set.yaml](eval/golden_set.yaml) trae **40 preguntas canónicas**
cubriendo A2/B1: present simple, past simple, present perfect, past progressive,
future, modals, articles, prepositions, comparatives, conditionals, vocabulary,
conversation, exercises, y 5 guardrail cases (off-domain + low-confidence).

**Antes de cerrar el baseline:**
1. Iván y Luis Ferro revisan cada ítem: ¿está alineado al syllabus del Fundamental Plus?
2. Ajustar `expected_sources`, `must_mention`, `must_not_mention` con el material real de `data/raw/`.
3. Añadir ítems faltantes (recomendado llegar a 50-60 para estadísticas más robustas).

## Módulos nuevos — referencia rápida

| Archivo | Responsabilidad |
|---|---|
| [src/config.py](src/config.py) | Configuración unificada (modelos, top-k, umbrales, flags) |
| [src/prompts.py](src/prompts.py) | Templates: tutor system prompt, context injection, contextual retrieval, rewriting, guardrails |
| [src/guardrails.py](src/guardrails.py) | `is_in_domain`, `detect_low_confidence`, heurística |
| [src/embeddings.py](src/embeddings.py) | BGE-M3 vía HuggingFace + Chroma |
| [src/document_loader.py](src/document_loader.py) | Parent-child splitting, metadata por unidad/nivel, contextual retrieval con cache |
| [src/retrieval.py](src/retrieval.py) | `AdvancedRetriever` = hybrid + rewriting + rerank + parent lookup |
| [src/llm_chain.py](src/llm_chain.py) | `LIARAGPipeline` — orquesta todo y emite `RAGResponse` tipado |
| [src/session_memory.py](src/session_memory.py) | SQLite: historial por student_id + feedback |
| [eval/golden_set.yaml](eval/golden_set.yaml) | 40 preguntas canónicas (propuesta inicial) |
| [eval/run_ragas.py](eval/run_ragas.py) | Benchmark RAGAS + métricas propias |
| [docker-compose.yml](docker-compose.yml) | LangFuse self-hosted con Postgres |

## Verificación end-to-end

1. `uv sync`
2. `ollama pull gemma2:9b-instruct-q4_K_M qwen2.5:3b-instruct-q4_K_M`
3. `docker compose up -d` (si usas LangFuse) → llenar `.env`
4. Poner archivos en `data/raw/` y `data/user/estudiantes_dummies.xlsx`
5. `uv run streamlit run app.py` → login admin → "Re-indexar"
6. Login estudiante → hacer 5 preguntas canónicas (una de cada tipo)
7. `python -m eval.run_ragas --all` → revisar `eval/results/llm_benchmark.csv`
8. Si LangFuse está activo → abrir `http://localhost:3000` y ver trazas

## Qué queda para las fases siguientes

- [ ] **Enriquecer golden set** con preguntas reales del uso en producción
  (consumir la tabla `feedback` de SQLite).
- [ ] **Fine-tune del re-ranker** cuando se tengan 200-300 interacciones con feedback.
- [ ] **Query routing** más sofisticado (sub-retrievers por categoría: gramática/vocab/conv).
- [ ] **Gamificación** (stars, levels) del plan original.
