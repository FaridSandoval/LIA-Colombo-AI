"""Reindex directo desde script (sin UI)."""
import sys
import logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

from src.document_loader import load_and_split_documents
from src.embeddings import create_or_load_vectorstore

print("=" * 60)
print("Iniciando reindex...")
print("=" * 60)

docs = load_and_split_documents()
print(f"\nChildren generados: {len(docs)}")

print("\nEmbeddings + persistencia en Chroma...")
vs = create_or_load_vectorstore(docs)
print(f"\nReindex completo. Vectorstore con {vs._collection.count()} chunks.")
