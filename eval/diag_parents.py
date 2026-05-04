"""Verificar el estado del parent_store vs los parent_ids de los chunks."""
import sys
sys.path.insert(0, ".")
from src.document_loader import load_parent_store
from src.embeddings import create_or_load_vectorstore

ps = load_parent_store()
print(f"Parent store: {len(ps)} entradas")
if ps:
    sample_keys = list(ps.keys())[:5]
    print(f"  Primeras 5 keys: {sample_keys}")

vs = create_or_load_vectorstore()
data = vs.get(limit=20, include=["metadatas"])
metas = data.get("metadatas", [])
print(f"\nChunks en Chroma (muestra 20):")
parent_ids_seen = set()
for m in metas:
    pid = m.get("parent_id", "NO_PARENT")
    parent_ids_seen.add(pid)
print(f"  Parent IDs únicos en muestra: {len(parent_ids_seen)}")
print(f"  Primeros 5: {list(parent_ids_seen)[:5]}")

if ps and parent_ids_seen:
    overlap = parent_ids_seen & set(ps.keys())
    print(f"\nOverlap entre parent_ids de Chroma y parent_store: {len(overlap)} de {len(parent_ids_seen)}")
