"""
Benchmark del pipeline LIA con RAGAS.

Uso:
    python -m eval.run_ragas --llm gemma2:9b
    python -m eval.run_ragas --all          # corre todos los candidatos secuencialmente
    python -m eval.run_ragas --baseline     # LLM directo sin RAG
    python -m eval.run_ragas --smoke-test   # solo 5 items para validar el pipeline
    python -m eval.run_ragas --skip-ragas   # omite mÃ©tricas RAGAS (no requiere OPENAI_API_KEY)

MÃ©tricas RAGAS (juez: GPT-4o via OPENAI_API_KEY):
    - faithfulness: Â¿la respuesta estÃ¡ soportada por el contexto?
    - answer_relevancy: Â¿la respuesta contesta la pregunta?
    - context_precision: Â¿los chunks recuperados son relevantes?
    - context_recall: Â¿recuperaste todos los chunks necesarios?

Extras propias:
    - keyword coverage (must_mention / must_not_mention)
    - latencia p50/p95
    - tasa de activaciÃ³n de guardrails
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from statistics import median

import yaml

from src.config import (
    LLM_BENCHMARK_CANDIDATES,
    LLM_MODEL_NAME,
    EVAL_DIR,
    EVAL_RESULTS_DIR,
    OLLAMA_BASE_URL,
)
from src.embeddings import create_or_load_vectorstore
from src.llm_chain import get_pipeline, RAGResponse


class BaselinePipeline:
    """Pipeline de lÃ­nea base: llama directo al LLM sin RAG ni retrieval."""

    def __init__(self, llm_model: str):
        self.llm_model = llm_model

    def query(self, user_query: str, user_info=None, conversation_history=None):
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=self.llm_model, base_url=OLLAMA_BASE_URL, temperature=0.2)
        response = llm.invoke([{"role": "user", "content": user_query}])
        return RAGResponse(
            answer=response.content,
            citations=[],
            retrieved_chunks=[],
            guardrail_triggered=None,
            llm_model=self.llm_model,
            trace_id=None,
        )


# Mock de usuario para el pipeline RAG (contexto de perfil requerido por los prompts)
_MOCK_USER_INFO = {
    "Student Name": "Estudiante de Prueba",
    "Course": "Fundamental Plus",
    "Status": "Activo",
    "Final Score": "70",
    "Teacher Feedback": "(sin feedback previo)",
}


def load_golden_set(path: Path | None = None) -> list[dict]:
    path = path or (EVAL_DIR / "golden_set.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("items", [])


def filter_smoke_test(golden: list[dict]) -> list[dict]:
    """Selecciona 5 items: 2 GRAMMAR, 2 VOCABULARY, 1 GUARDRAIL_*."""
    grammar = [i for i in golden if i.get("category", "").upper() == "GRAMMAR"]
    vocabulary = [i for i in golden if i.get("category", "").upper() == "VOCABULARY"]
    guardrail = [i for i in golden if i.get("category", "").upper().startswith("GUARDRAIL_")]

    selected = grammar[:2] + vocabulary[:2] + guardrail[:1]

    # Fallback: completar hasta 5 con los primeros items no incluidos
    if len(selected) < 5:
        seen_ids = {i["id"] for i in selected}
        for item in golden:
            if item["id"] not in seen_ids and len(selected) < 5:
                selected.append(item)

    return selected[:5]


def keyword_coverage(answer: str, must_mention: list[str], must_not_mention: list[str]) -> dict:
    a = (answer or "").lower()
    hits = [kw for kw in (must_mention or []) if kw.lower() in a]
    misses = [kw for kw in (must_mention or []) if kw.lower() not in a]
    violations = [kw for kw in (must_not_mention or []) if kw.lower() in a]
    mention_rate = len(hits) / len(must_mention) if must_mention else 1.0
    return {
        "mention_rate": mention_rate,
        "mentions_hit": hits,
        "mentions_missed": misses,
        "violations": violations,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = int(round((len(s) - 1) * p))
    return s[k]


def run_pipeline_on_golden_set(
    pipeline, golden: list[dict], baseline: bool = False
) -> list[dict]:
    """Ejecuta el pipeline sobre cada item y colecciona resultados brutos."""
    rows = []
    for item in golden:
        t0 = time.perf_counter()
        try:
            if baseline:
                # Modo baseline: sin user_info ni historial
                resp = pipeline.query(user_query=item["question"])
            else:
                resp = pipeline.query(
                    user_query=item["question"],
                    user_info=_MOCK_USER_INFO,
                    conversation_history=[],
                )
            answer = resp.answer
            contexts = [c.get("full_text", c.get("snippet", "")) for c in resp.citations]
            guardrail = resp.guardrail_triggered or ""
        except Exception as e:
            answer = f"<error: {e}>"
            contexts = []
            guardrail = "error"
        latency_s = time.perf_counter() - t0

        cov = keyword_coverage(
            answer,
            item.get("must_mention", []),
            item.get("must_not_mention", []),
        )
        rows.append({
            "id": item["id"],
            "category": item["category"],
            "language": item["language"],
            "level": item.get("level", ""),
            "topic": item.get("topic", ""),
            "question": item["question"],
            "ground_truth": item["ground_truth"],
            "answer": answer,
            "contexts": contexts,
            "guardrail": guardrail,
            "latency_s": round(latency_s, 3),
            **cov,
        })
        print(f"  [{item['id']}] {latency_s:.2f}s guardrail={guardrail} "
              f"mention_rate={cov['mention_rate']:.2f}")
    return rows


def compute_ragas_metrics(rows: list[dict]):
    """
    Calcula métricas RAGAS usando GPT-4o-mini como juez y text-embedding-3-small.
    Devuelve None si falla o si no hay items válidos.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.run_config import RunConfig
        from ragas.metrics import (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings

        # Items con guardrail no aplican para las métricas RAGAS estándar
        ragas_rows = [r for r in rows if not r["guardrail"]]
        if not ragas_rows:
            return None

        ds = Dataset.from_list([{
            "question": r["question"],
            "answer": r["answer"],
            "contexts": r["contexts"] or ["(no context)"],
            "ground_truth": r["ground_truth"],
        } for r in ragas_rows])

        judge_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
        judge_emb = OpenAIEmbeddings(model="text-embedding-3-small")

        # RunConfig para evitar timeouts y rate limits con OpenAI
        run_config = RunConfig(
            max_workers=4,        # default 16 - bajar para evitar rate limits
            timeout=180,          # default 60s - subir para gpt-4o lento
            max_retries=5,        # reintentos antes de dar NaN
        )

        result = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=judge_llm,
            embeddings=judge_emb,
            run_config=run_config,
        )
        return result
    except ImportError as e:
        print(f"  [WARN] RAGAS no disponible ({e}). Saltando métricas RAGAS.")
        return None
    except Exception as e:
        import traceback
        print(f"  [WARN] Error calculando RAGAS: {type(e).__name__}: {e}")
        print(f"  [TRACEBACK]:")
        traceback.print_exc()
        return None


def write_detailed_csv(
    rows: list[dict], out_path: Path, llm_model: str, mode: str = "rag"
) -> None:
    fieldnames = [
        "llm_model", "mode", "id", "category", "language", "level", "topic",
        "question", "ground_truth", "answer",
        "guardrail", "latency_s", "mention_rate",
        "mentions_hit", "mentions_missed", "violations",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "llm_model": llm_model,
                "mode": mode,
                "id": r["id"],
                "category": r["category"],
                "language": r["language"],
                "level": r["level"],
                "topic": r["topic"],
                "question": r["question"],
                "ground_truth": r["ground_truth"],
                "answer": r["answer"],
                "guardrail": r["guardrail"],
                "latency_s": r["latency_s"],
                "mention_rate": r["mention_rate"],
                "mentions_hit": ", ".join(r["mentions_hit"]),
                "mentions_missed": ", ".join(r["mentions_missed"]),
                "violations": ", ".join(r["violations"]),
            })


def summarize(
    rows: list[dict], llm_model: str, ragas_result, mode: str = "rag"
) -> dict:
    latencies = [r["latency_s"] for r in rows]
    mention_rates = [r["mention_rate"] for r in rows]
    guardrail_counts = {}
    for r in rows:
        if r["guardrail"]:
            guardrail_counts[r["guardrail"]] = guardrail_counts.get(r["guardrail"], 0) + 1
    violations_total = sum(len(r["violations"]) for r in rows)

    summary = {
        "llm_model": llm_model,
        "mode": mode,
        "n_items": len(rows),
        "mean_mention_rate": round(sum(mention_rates) / max(len(mention_rates), 1), 4),
        "guardrail_activations": guardrail_counts,
        "hallucination_violations": violations_total,
        "latency_p50_s": round(median(latencies) if latencies else 0, 3),
        "latency_p95_s": round(percentile(latencies, 0.95), 3),
        "latency_mean_s": round(sum(latencies) / max(len(latencies), 1), 3),
    }
    if ragas_result is not None:
        try:
            scores = ragas_result.scores if hasattr(ragas_result, "scores") else ragas_result
            if isinstance(scores, list) and scores:
                keys = scores[0].keys()
                for k in keys:
                    summary[f"ragas_{k}"] = round(
                        sum(s[k] for s in scores) / len(scores), 4
                    )
            elif isinstance(scores, dict):
                for k, v in scores.items():
                    try:
                        summary[f"ragas_{k}"] = round(float(v), 4)
                    except (TypeError, ValueError):
                        summary[f"ragas_{k}"] = str(v)
        except Exception as e:
            summary["ragas_error"] = str(e)
    return summary


def append_benchmark_row(summary: dict, bench_csv: Path) -> None:
    exists = bench_csv.exists()
    existing_fields: list[str] = []
    if exists:
        with bench_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
    fieldnames = list(dict.fromkeys(existing_fields + list(summary.keys())))

    rows_to_write: list[dict] = []
    if exists:
        with bench_csv.open("r", encoding="utf-8") as f:
            rows_to_write = list(csv.DictReader(f))
    flat = dict(summary)
    flat["guardrail_activations"] = json.dumps(summary.get("guardrail_activations", {}))
    rows_to_write.append(flat)

    with bench_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows_to_write:
            if "guardrail_activations" in r and not isinstance(r["guardrail_activations"], str):
                r["guardrail_activations"] = json.dumps(r["guardrail_activations"])
            writer.writerow(r)


def run_for_model(
    llm_model: str,
    golden: list[dict],
    baseline: bool = False,
    skip_ragas: bool = False,
) -> dict:
    mode = "baseline" if baseline else "rag"
    print(f"\n=== Benchmarking {llm_model} [{mode}] ===")

    if baseline:
        pipeline = BaselinePipeline(llm_model)
    else:
        vs = create_or_load_vectorstore()
        pipeline = get_pipeline(vs, llm_model=llm_model)

    rows = run_pipeline_on_golden_set(pipeline, golden, baseline=baseline)

    model_slug = llm_model.replace("/", "_").replace(":", "_")
    suffix = "_baseline" if baseline else ""
    detail_csv = EVAL_RESULTS_DIR / f"detail_{model_slug}{suffix}.csv"
    write_detailed_csv(rows, detail_csv, llm_model, mode=mode)
    print(f"  Detalle escrito en {detail_csv}")

    ragas_result = None
    if not skip_ragas:
        print("  Calculando RAGAS...")
        ragas_result = compute_ragas_metrics(rows)

    summary = summarize(rows, llm_model, ragas_result, mode=mode)
    print(f"  Resumen: {json.dumps(summary, ensure_ascii=False, indent=2)}")

    bench_csv = EVAL_RESULTS_DIR / "llm_benchmark.csv"
    append_benchmark_row(summary, bench_csv)
    print(f"  Fila aÃ±adida a {bench_csv}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark RAGAS para LIA-Colombo AI")
    parser.add_argument("--llm", default=LLM_MODEL_NAME, help="Modelo Ollama a evaluar")
    parser.add_argument("--all", action="store_true",
                        help="Correr todos los candidatos de LLM_BENCHMARK_CANDIDATES")
    parser.add_argument("--baseline", action="store_true",
                        help="Modo baseline: LLM directo sin RAG")
    parser.add_argument("--smoke-test", action="store_true", dest="smoke_test",
                        help="Correr solo 5 items para validar el pipeline rÃ¡pidamente")
    parser.add_argument("--skip-ragas", action="store_true", dest="skip_ragas",
                        help="Omitir cÃ¡lculo de mÃ©tricas RAGAS (no requiere OPENAI_API_KEY)")
    parser.add_argument("--golden", default=None,
                        help="Ruta a golden_set.yaml (default: eval/golden_set.yaml)")
    parser.add_argument("--include-category", action="append", dest="include_categories",
                        metavar="CATEGORY",
                        help="Solo correr items de esta categoría (puede repetirse)")
    args = parser.parse_args()

    # Validar API key antes de empezar si se van a calcular métricas RAGAS
    if not args.skip_ragas:
        if not os.getenv("OPENAI_API_KEY"):
            print(
                "ERROR: OPENAI_API_KEY no está configurada en el entorno.\n"
                "Agrégala al archivo .env o usa --skip-ragas para omitir las métricas RAGAS."
            )
            sys.exit(1)

    golden = load_golden_set(Path(args.golden) if args.golden else None)
    print(f"Golden set: {len(golden)} items")

    if args.include_categories:
        categories = {c.upper() for c in args.include_categories}
        before = len(golden)
        golden = [i for i in golden if i.get("category", "").upper() in categories]
        print(f"[--include-category] Filtro: {before} -> {len(golden)} items (categorías: {categories})")

    if args.smoke_test:
        golden = filter_smoke_test(golden)
        print(f"[SMOKE TEST] Corriendo solo {len(golden)} items para validar el pipeline.")

    if args.all:
        for m in LLM_BENCHMARK_CANDIDATES:
            run_for_model(m, golden, baseline=args.baseline, skip_ragas=args.skip_ragas)
    else:
        run_for_model(args.llm, golden, baseline=args.baseline, skip_ragas=args.skip_ragas)


if __name__ == "__main__":
    sys.exit(main())


