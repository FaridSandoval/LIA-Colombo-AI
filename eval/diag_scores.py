"""Diagnostico: ver scores reales de retrieval para preguntas que activan low_confidence."""
import sys
sys.path.insert(0, ".")
from src.embeddings import create_or_load_vectorstore
from src.retrieval import AdvancedRetriever
from src.config import LOW_CONFIDENCE_THRESHOLD

queries = [
    ("G01", "Cuando uso 'do' y cuando uso 'does'?"),
    ("G07", "Cuando se usa el past progressive?"),
    ("G05", "Cual es el pasado de 'go' y 'eat'?"),
    ("G09", "Como se forma el present perfect?"),
    ("G10", "When do I use 'for' and when do I use 'since'?"),
]

print(f"LOW_CONFIDENCE_THRESHOLD actual: {LOW_CONFIDENCE_THRESHOLD}")
print("=" * 80)

vs = create_or_load_vectorstore()
retriever = AdvancedRetriever(vs)

for qid, q in queries:
    print(f"\n[{qid}] {q}")
    ranked = retriever.search(q)
    scores = [s for _, s in ranked]
    if not scores:
        print("  -> SIN RESULTADOS")
        continue
    top = max(scores)
    pasa = "PASA" if top >= LOW_CONFIDENCE_THRESHOLD else "RECHAZA"
    print(f"  Top score: {top:.4f}  -> {pasa}")
    print(f"  Top 5 scores: {[round(s, 4) for s in sorted(scores, reverse=True)[:5]]}")
    if ranked:
        top_doc = ranked[0][0]
        src = top_doc.metadata.get("source", "N/A").split("\\")[-1].split("/")[-1]
        preview = top_doc.page_content[:120].replace("\n", " ")
        print(f"  Top doc: {src}")
        print(f"  Preview: {preview}...")
