"""Diagnostico capa por capa: ver que devuelve cada etapa del pipeline."""
import sys
sys.path.insert(0, ".")
from src.embeddings import create_or_load_vectorstore
from src.retrieval import AdvancedRetriever, rerank_documents, resolve_parents

q = "Cuando uso 'do' y cuando uso 'does'?"

print(f"Query: {q}")
print("=" * 80)

vs = create_or_load_vectorstore()
retriever = AdvancedRetriever(vs)

# Capa 1: Hybrid retrieve crudo (sin rerank, sin parents)
print("\n[CAPA 1] Hybrid retrieve (sin rewriting):")
hybrid_no_rw = retriever.hybrid.retrieve(q, top_k=10, use_rewriting=False)
print(f"  Candidatos: {len(hybrid_no_rw)}")
for i, (doc, score) in enumerate(hybrid_no_rw[:3], 1):
    src = doc.metadata.get("source", "N/A").split("\\")[-1].split("/")[-1]
    print(f"  {i}. score={score:.4f} src={src}")

print("\n[CAPA 1b] Hybrid retrieve (con rewriting):")
hybrid_rw = retriever.hybrid.retrieve(q, top_k=10, use_rewriting=True)
print(f"  Candidatos: {len(hybrid_rw)}")
for i, (doc, score) in enumerate(hybrid_rw[:3], 1):
    src = doc.metadata.get("source", "N/A").split("\\")[-1].split("/")[-1]
    print(f"  {i}. score={score:.4f} src={src}")

# Capa 2: Rerank
print("\n[CAPA 2] Rerank:")
reranked = rerank_documents(q, hybrid_rw, top_k=5)
print(f"  Reranked: {len(reranked)}")
for i, (doc, score) in enumerate(reranked, 1):
    src = doc.metadata.get("source", "N/A").split("\\")[-1].split("/")[-1]
    pid = doc.metadata.get("parent_id", "NO_PARENT")
    print(f"  {i}. score={score:.4f} src={src} parent_id={pid}")

# Capa 3: Resolve parents
print("\n[CAPA 3] Resolve parents:")
final = resolve_parents(reranked)
print(f"  Final: {len(final)}")
for i, (doc, score) in enumerate(final, 1):
    src = doc.metadata.get("source", "N/A").split("\\")[-1].split("/")[-1]
    print(f"  {i}. score={score:.4f} src={src}")

print("\n[CAPA TOTAL] retriever.search():")
total = retriever.search(q)
print(f"  Total: {len(total)}")
