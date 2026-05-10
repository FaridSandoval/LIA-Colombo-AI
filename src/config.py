"""Configuración centralizada del pipeline RAG LIA-Colombo AI."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# 1. RUTAS DEL SISTEMA DE ARCHIVOS
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
USER_DATA_DIR = DATA_DIR / "user"
FEEDBACK_DIR = DATA_DIR / "feedback"
SESSIONS_DIR = DATA_DIR / "sessions"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
PARENT_DOCS_DIR = DATA_DIR / "parent_docs"
CONTEXTUAL_CACHE_DIR = DATA_DIR / "contextual_cache"
EVAL_DIR = BASE_DIR / "eval"
EVAL_RESULTS_DIR = EVAL_DIR / "results"

for d in (RAW_DATA_DIR, USER_DATA_DIR, FEEDBACK_DIR, SESSIONS_DIR,
          CHROMA_DB_DIR, PARENT_DOCS_DIR, CONTEXTUAL_CACHE_DIR,
          EVAL_DIR, EVAL_RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. EMBEDDINGS (BGE-M3 multilingüe)
# ==========================================
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "lia_bge_m3")

# ==========================================
# 3. CHUNKING (Parent-Child)
# ==========================================
PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", 1800))
PARENT_CHUNK_OVERLAP = int(os.getenv("PARENT_CHUNK_OVERLAP", 200))
CHILD_CHUNK_SIZE = int(os.getenv("CHILD_CHUNK_SIZE", 350))
CHILD_CHUNK_OVERLAP = int(os.getenv("CHILD_CHUNK_OVERLAP", 50))

# Separadores conscientes de estructura gramatical (listas, ejemplos, reglas)
CHUNK_SEPARATORS = ["\n\n", "\n", "• ", "- ", "* ", "1. ", "2. ",
                    ". ", "! ", "? ", "; ", " ", ""]

# Backward compat (document_loader legacy puede importarlos)
CHUNK_SIZE = CHILD_CHUNK_SIZE
CHUNK_OVERLAP = CHILD_CHUNK_OVERLAP

# ==========================================
# 4. INFERENCIA (OpenAI)
# ==========================================
# Clave API — se lee desde st.secrets en Streamlit Cloud, o desde .env local
def _get_openai_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    except Exception:
        return os.getenv("OPENAI_API_KEY", "")

OPENAI_API_KEY: str = _get_openai_key()

# Deprecated — sólo conservado para compatibilidad con guardrails.py que lo importa
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modelo principal
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.2))

# Candidatos para benchmark RAGAS
LLM_BENCHMARK_CANDIDATES = ["gpt-4o-mini", "gpt-4o"]

# LLM auxiliar para routing, contextual retrieval y guardrails
LLM_UTILITY_MODEL = os.getenv("LLM_UTILITY_MODEL", "gpt-4o-mini")

# ==========================================
# 5. RETRIEVAL AVANZADO
# ==========================================
# Hybrid search
HYBRID_BM25_WEIGHT = float(os.getenv("HYBRID_BM25_WEIGHT", 0.3))
HYBRID_VECTOR_WEIGHT = float(os.getenv("HYBRID_VECTOR_WEIGHT", 0.7))

# Top-k por etapa
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", 20))   # tras hybrid
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", 5))          # tras cross-encoder

# Re-ranker
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
RERANKER_USE_FP16 = os.getenv("RERANKER_USE_FP16", "true").lower() == "true"

# Contextual Retrieval (Anthropic, sep 2024)
ENABLE_CONTEXTUAL_RETRIEVAL = os.getenv("ENABLE_CONTEXTUAL_RETRIEVAL", "true").lower() == "true"
CONTEXTUAL_MAX_WORDS = int(os.getenv("CONTEXTUAL_MAX_WORDS", 60))

# Query rewriting + HyDE
ENABLE_QUERY_REWRITING = os.getenv("ENABLE_QUERY_REWRITING", "true").lower() == "true"

# Umbral bajo-confianza (para guardrail "no sé")
LOW_CONFIDENCE_THRESHOLD = float(os.getenv("LOW_CONFIDENCE_THRESHOLD", 0.05))

# ==========================================
# 6. GUARDRAILS
# ==========================================
ENABLE_DOMAIN_GUARDRAIL = os.getenv("ENABLE_DOMAIN_GUARDRAIL", "true").lower() == "true"
ENABLE_LOW_CONFIDENCE_GUARDRAIL = os.getenv("ENABLE_LOW_CONFIDENCE_GUARDRAIL", "true").lower() == "true"
# Reranker: descarga ~1.1 GB en primer uso — desactivado por default en Cloud free tier
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "false").lower() == "true"

# ==========================================
# 7. OBSERVABILIDAD (LangFuse self-hosted)
# ==========================================
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
ENABLE_LANGFUSE = bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

# ==========================================
# 8. PROMPT DEFAULT (fallback)
# ==========================================
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Eres un asistente pedagógico experto del Centro Cultural Colombo Americano. "
    "Utiliza únicamente el contexto proporcionado para responder de forma clara, "
    "didáctica y enfocada en el aprendizaje del inglés. "
    "Si la respuesta no está en el contexto, indícalo sin inventar."
)
