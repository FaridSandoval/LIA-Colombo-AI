"""
Benchmark del pipeline LIA con RAGAS.

Uso:
    python -m eval.run_ragas --llm gemma2:9b-instruct-q4_K_M
    python -m eval.run_ragas --all   # corre los 3 candidatos secuencialmente

Métricas RAGAS:
    - faithfulness: ¿la respuesta está soportada por el contexto?
    - answer_relevancy: ¿la respuesta contesta la pregunta?
    - context_precision: ¿los chunks recuperados son relevantes?
    - context_recall: ¿recuperaste todos los chunks necesarios?

Extras propias:
    - keyword coverage (must_mention / must_not_mention)
    - latencia p50/p95
    - tasa de activación de guardrails
"""
from __future__ import annotations
import argparse
import csv
import json
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
from src.embeddings import create_or_load_vectorstore, get_embedding_model
from src.llm_chain import get_pipeline


def load_golden_set(path: Path | None = None) -> list[dict]:
    path = path or (EVAL_DIR / "golden_set.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data.get("items", [])


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


def run_pipeline_on_golden_set(pipeline, golden: list[dict]) -> list[dict]:
    """Ejecuta el pipeline sobre cada item y colecciona resultados brutos."""
    rows = []
    for item in golden:
        t0 = time.perf_counter()
        try:
            resp = pipeline.query(user_query=item["question"])
            answer = resp.answer
            contexts = [c.get("snippet", "") for c in resp.citations]
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
    Intenta calcular métricas de RAGAS. Si RAGAS no está instalado o falla,
    devuelve None y seguimos con las métricas propias.
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            faithfulness, answer_relevancy,
            context_precision, context_recall,
        )
        from langchain_ollama import ChatOllama, OllamaEmbeddings

        # Filtramos los que activan guardrail — no aplican las métricas RAGAS estándar
        ragas_rows = [r for r in rows if not r["guardrail"]]
        if not ragas_rows:
            return None

        ds = Dataset.from_list([{
            "question": r["question"],
            "answer": r["answer"],
            "contexts": r["contexts"] or ["(no context)"],
            "ground_truth": r["ground_truth"],
        } for r in ragas_rows])

        # Usar el utility LLM (más rápido) como juez; embeddings: bge-m3 ya configurado
        from src.config import LLM_UTILITY_MODEL
        judge_llm = ChatOllama(
            model=LLM_UTILITY_MODEL, base_url=OLLAMA_BASE_URL, temperature=0.0,
        )
        judge_emb = get_embedding_model()

        result = evaluate(
            ds,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=judge_llm,
            embeddings=judge_emb,
        )
        return result
    except ImportError as e:
        print(f"  ⚠ RAGAS no disponible ({e}). Saltando métricas RAGAS.")
        return None
    except Exception as e:
        print(f"  ⚠ Error calculando RAGAS: {e}")
        return None


def write_detailed_csv(rows: list[dict], out_path: Path, llm_model: str) -> None:
    fieldnames = [
        "llm_model", "id", "category", "language", "level", "topic",
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


def summarize(rows: list[dict], llm_model: str, ragas_result) -> dict:
    latencies = [r["latency_s"] for r in rows]
    mention_rates = [r["mention_rate"] for r in rows]
    guardrail_counts = {}
    for r in rows:
        if r["guardrail"]:
            guardrail_counts[r["guardrail"]] = guardrail_counts.get(r["guardrail"], 0) + 1
    violations_total = sum(len(r["violations"]) for r in rows)

    summary = {
        "llm_model": llm_model,
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
            # RAGAS result objeto → dict por métrica
            scores = ragas_result.scores if hasattr(ragas_result, "scores") else ragas_result
            if isinstance(scores, list) and scores:
                # promedio por métrica
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
    # Unir todas las keys vistas en ejecuciones previas
    existing_fields: list[str] = []
    if exists:
        with bench_csv.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
    fieldnames = list(dict.fromkeys(existing_fields + list(summary.keys())))

    # Re-escribir con el superset de columnas
    rows_to_write: list[dict] = []
    if exists:
        with bench_csv.open("r", encoding="utf-8") as f:
            rows_to_write = list(csv.DictReader(f))
    # Flatten guardrail_activations para CSV
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


def run_for_model(llm_model: str, golden: list[dict]) -> dict:
    print(f"\n=== Benchmarking {llm_model} ===")
    vs = create_or_load_vectorstore()
    pipeline = get_pipeline(vs, llm_model=llm_model)

    rows = run_pipeline_on_golden_set(pipeline, golden)

    detail_csv = EVAL_RESULTS_DIR / f"detail_{llm_model.replace('/', '_').replace(':', '_')}.csv"
    write_detailed_csv(rows, detail_csv, llm_model)
    print(f"  Detalle escrito en {detail_csv}")

    print("  Calculando RAGAS...")
    ragas_result = compute_ragas_metrics(rows)

    summary = summarize(rows, llm_model, ragas_result)
    print(f"  Resumen: {json.dumps(summary, ensure_ascii=False, indent=2)}")

    bench_csv = EVAL_RESULTS_DIR / "llm_benchmark.csv"
    append_benchmark_row(summary, bench_csv)
    print(f"  Fila añadida a {bench_csv}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Benchmark RAGAS para LIA-Colombo AI")
    parser.add_argument("--llm", default=LLM_MODEL_NAME, help="Modelo Ollama a evaluar")
    parser.add_argument("--all", action="store_true",
                        help="Correr los 3 candidatos del benchmark")
    parser.add_argument("--golden", default=None,
                        help="Ruta a golden_set.yaml (default: eval/golden_set.yaml)")
    args = parser.parse_args()

    golden = load_golden_set(Path(args.golden) if args.golden else None)
    print(f"Golden set: {len(golden)} items")

    if args.all:
        for m in LLM_BENCHMARK_CANDIDATES:
            run_for_model(m, golden)
    else:
        run_for_model(args.llm, golden)


if __name__ == "__main__":
    sys.exit(main())
