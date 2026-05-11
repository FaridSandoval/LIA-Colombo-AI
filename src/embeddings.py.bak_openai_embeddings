"""Vector store + embeddings multilingües BGE-M3."""
from __future__ import annotations
import logging
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_DEVICE,
    CHROMA_COLLECTION_NAME,
    CHROMA_DB_DIR,
)

logger = logging.getLogger(__name__)


def _resolve_device() -> str:
    if EMBEDDING_DEVICE != "auto":
        return EMBEDDING_DEVICE
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_embedding_model() -> HuggingFaceEmbeddings:
    """Instancia BGE-M3 vía sentence-transformers (HuggingFace)."""
    device = _resolve_device()
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )


def create_or_load_vectorstore(documents=None) -> Chroma:
    """
    Carga o reconstruye el vectorstore Chroma.

    - `documents` pasados explícitamente: los indexa (scripts manuales).
    - Colección vacía o inexistente: indexa automáticamente desde data/raw/.
    - Colección con documentos: devuelve tal cual (path normal en producción).
    """
    embeddings = get_embedding_model()
    vector_store = Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DB_DIR),
    )

    if documents:
        batch_size = 5000
        for i in range(0, len(documents), batch_size):
            vector_store.add_documents(documents[i : i + batch_size])
        return vector_store

    try:
        count = vector_store._collection.count()
    except Exception:
        count = 0

    if count == 0:
        logger.info("Vectorstore vacío — indexando corpus desde data/raw/ ...")
        from src.document_loader import load_and_split_documents
        docs = load_and_split_documents()
        if docs:
            batch_size = 5000
            for i in range(0, len(docs), batch_size):
                vector_store.add_documents(docs[i : i + batch_size])
            logger.info(f"Indexación completa: {len(docs)} documentos cargados.")

    return vector_store
