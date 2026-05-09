"""
Retrieval avanzado:
- Hybrid Search (BM25 + dense) con RRF.
- Re-ranking con cross-encoder BGE-reranker-v2-m3.
- Contextual Retrieval (resumen pre-embed, en document_loader).
- Query rewriting / HyDE.
- Metadata filtering por nivel/unidad del estudiante.
"""
from __future__ import annotations
import json
import logging
from typing import List, Optional, Tuple

from langchain_core.documents import Document
from langchain_chroma import Chroma

from src.config import (
    HYBRID_BM25_WEIGHT,
    HYBRID_VECTOR_WEIGHT,
    RETRIEVAL_TOP_K,
    RERANK_TOP_K,
    RERANKER_MODEL_NAME,
    RERANKER_USE_FP16,
    ENABLE_QUERY_REWRITING,
    OLLAMA_BASE_URL,
    LLM_UTILITY_MODEL,
)
from src.prompts import QUERY_REWRITE_PROMPT
from src.document_loader import load_parent_store

logger = logging.getLogger(__name__)


# ==========================================
# Reranker (singleton)
# ==========================================
_reranker = None


def get_reranker():
    """Inicializa el cross-encoder BGE-reranker-v2-m3 (una sola vez)."""
    global _reranker
    if _reranker is not None:
        return _reranker
    try:
        from FlagEmbedding import FlagReranker
        _reranker = FlagReranker(RERANKER_MODEL_NAME, use_fp16=RERANKER_USE_FP16)
        logger.info(f"Reranker {RERANKER_MODEL_NAME} cargado.")
    except Exception as e:
        logger.warning(f"No se pudo cargar reranker: {e}")
        _reranker = None
    return _reranker


# ==========================================
# Query rewriting / HyDE
# ==========================================
_rewrite_llm = None


def _get_rewrite_llm():
    global _rewrite_llm
    if _rewrite_llm is not None:
        return _rewrite_llm
    try:
        from langchain_ollama import ChatOllama
        _rewrite_llm = ChatOllama(
            model=LLM_UTILITY_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.0,
        )
    except Exception as e:
        logger.warning(f"LLM de rewriting no disponible: {e}")
        _rewrite_llm = None
    return _rewrite_llm


def rewrite_query(query: str) -> List[str]:
    """Genera [query_original, query_es, query_en, hyde]."""
    variants = [query]
    if not ENABLE_QUERY_REWRITING:
        return variants

    llm = _get_rewrite_llm()
    if llm is None:
        return variants

    try:
        resp = llm.invoke(QUERY_REWRITE_PROMPT.format(query=query)).content.strip()
        # Extraer JSON robusto
        start = resp.find("{")
        end = resp.rfind("}")
        if start == -1 or end == -1:
            return variants
        data = json.loads(resp[start:end + 1])
        for key in ("es", "en", "hyde"):
            val = data.get(key, "").strip()
            if val and val not in variants:
                variants.append(val)
    except Exception as e:
        logger.debug(f"Rewriting falló: {e}")
    return variants


# ==========================================
# Hybrid retriever (BM25 + vectorial con RRF)
# ==========================================
class HybridRetriever:
    """
    Combina BM25 lexical + Chroma semántico usando Reciprocal Rank Fusion.
    No usamos EnsembleRetriever de LangChain porque queremos control fino sobre:
    - múltiples queries (HyDE)
    - metadata filtering
    - RRF explícito
    """

    def __init__(self, vector_store: Chroma, bm25_documents: Optional[List[Document]] = None):
        self.vector_store = vector_store
        self._bm25 = None
        self._bm25_corpus: List[Document] = []
        self._bm25_tokens: List[List[str]] = []
        if bm25_documents:
            self._build_bm25(bm25_documents)

    def _build_bm25(self, documents: List[Document]) -> None:
        try:
            from rank_bm25 import BM25Okapi
            self._bm25_corpus = documents
            self._bm25_tokens = [
                d.page_content.lower().split() for d in documents
            ]
            self._bm25 = BM25Okapi(self._bm25_tokens)
            logger.info(f"BM25 index construido con {len(documents)} documentos.")
        except Exception as e:
            logger.warning(f"No se pudo construir BM25: {e}")
            self._bm25 = None

    def rebuild_bm25_from_store(self) -> None:
        """Reconstruye BM25 desde los parents persistidos en disco."""
        parents = load_parent_store()
        if parents:
            self._build_bm25(list(parents.values()))

    def _bm25_search(self, query: str, k: int) -> List[Tuple[Document, float]]:
        if self._bm25 is None or not self._bm25_corpus:
            return []
        import numpy as np
        tokens = query.lower().split()
        scores = self._bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:k]
        return [
            (self._bm25_corpus[i], float(scores[i]))
            for i in top_idx
            if scores[i] > 0
        ]

    def _vector_search(
        self,
        query: str,
        k: int,
        filter_dict: Optional[dict] = None,
    ) -> List[Tuple[Document, float]]:
        try:
            results = self.vector_store.similarity_search_with_score(
                query, k=k, filter=filter_dict,
            )
            # Chroma: score = distancia (menor = mejor). Convertimos a similitud.
            return [(doc, 1.0 / (1.0 + score)) for doc, score in results]
        except Exception as e:
            logger.warning(f"Vector search falló: {e}")
            return []

    @staticmethod
    def _rrf_fuse(
        ranked_lists: List[List[Tuple[Document, float]]],
        weights: List[float],
        k: int = 60,
    ) -> List[Tuple[Document, float]]:
        """Reciprocal Rank Fusion ponderado. `k` amortiguador estándar."""
        scores: dict = {}
        docs_by_key: dict = {}
        for ranked, weight in zip(ranked_lists, weights):
            for rank, (doc, _) in enumerate(ranked):
                # Usamos page_content como key — podría chocar si hay duplicados exactos
                key = doc.page_content[:200]
                scores[key] = scores.get(key, 0.0) + weight * (1.0 / (k + rank + 1))
                docs_by_key[key] = doc
        fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [(docs_by_key[key], score) for key, score in fused]

    def retrieve(
        self,
        query: str,
        top_k: int = RETRIEVAL_TOP_K,
        filter_dict: Optional[dict] = None,
        use_rewriting: bool = True,
    ) -> List[Tuple[Document, float]]:
        """
        Ejecuta hybrid search. Si use_rewriting, genera variantes y las fusiona.
        Devuelve top_k Documents con scores fusionados.
        """
        queries = rewrite_query(query) if use_rewriting else [query]

        all_ranked: List[List[Tuple[Document, float]]] = []
        weights: List[float] = []

        for q in queries:
            vec = self._vector_search(q, k=top_k, filter_dict=filter_dict)
            if vec:
                all_ranked.append(vec)
                weights.append(HYBRID_VECTOR_WEIGHT)

        # BM25 solo en la query original (es match léxico, no se beneficia de HyDE)
        lex = self._bm25_search(query, k=top_k)
        if lex:
            all_ranked.append(lex)
            weights.append(HYBRID_BM25_WEIGHT)

        if not all_ranked:
            return []

        fused = self._rrf_fuse(all_ranked, weights)
        return fused[:top_k]


# ==========================================
# Re-ranking
# ==========================================
def rerank_documents(
    query: str,
    candidates: List[Tuple[Document, float]],
    top_k: int = RERANK_TOP_K,
) -> List[Tuple[Document, float]]:
    """Re-rankea con cross-encoder. Si no disponible, devuelve los primeros top_k."""
    if not candidates:
        return []
    reranker = get_reranker()
    if reranker is None:
        return candidates[:top_k]

    pairs = [[query, doc.page_content] for doc, _ in candidates]
    try:
        scores = reranker.compute_score(pairs, normalize=True)
        if isinstance(scores, float):
            scores = [scores]
        reranked = sorted(
            zip([c[0] for c in candidates], scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return reranked[:top_k]
    except Exception as e:
        logger.warning(f"Reranker falló: {e}")
        return candidates[:top_k]


# ==========================================
# Parent lookup (small-to-big)
# ==========================================
_parent_store_cache: Optional[dict] = None


def _get_parent_store() -> dict:
    global _parent_store_cache
    if _parent_store_cache is None:
        _parent_store_cache = load_parent_store()
    return _parent_store_cache


def resolve_parents(
    ranked: List[Tuple[Document, float]],
) -> List[Tuple[Document, float]]:
    """
    Small-to-big: si el child tiene parent_id, devolvemos el parent chunk
    (contexto más rico para el LLM). Dedup por parent_id.
    """
    parent_store = _get_parent_store()
    if not parent_store:
        return ranked

    seen = set()
    result: List[Tuple[Document, float]] = []
    for doc, score in ranked:
        pid = doc.metadata.get("parent_id")
        if pid and pid in parent_store and pid not in seen:
            seen.add(pid)
            result.append((parent_store[pid], score))
        elif not pid:
            result.append((doc, score))
    return result


# ==========================================
# API principal — Advanced Retriever
# ==========================================
class AdvancedRetriever:
    """
    Fachada que combina: query rewriting → hybrid search → rerank → parent lookup.
    """

    def __init__(self, vector_store: Chroma):
        self.vector_store = vector_store
        self.hybrid = HybridRetriever(vector_store)
        self.hybrid.rebuild_bm25_from_store()

    def search(
        self,
        query: str,
        student_level: Optional[str] = None,
        student_unit: Optional[int] = None,
        top_k: int = RERANK_TOP_K,
    ) -> List[Tuple[Document, float]]:
        """
        Pipeline completo. Aplica filter por nivel/unidad si se proveen
        (y solo si la colección tiene documentos con esos metadatos).
        """
        filter_dict = None
        conds = []
        if student_level:
            conds.append({"level": student_level})
        if student_unit:
            conds.append({"unit": student_unit})
        if len(conds) == 1:
            filter_dict = conds[0]
        elif len(conds) > 1:
            filter_dict = {"$and": conds}

        # 1) Hybrid + rewriting
        candidates = self.hybrid.retrieve(
            query, top_k=RETRIEVAL_TOP_K, filter_dict=filter_dict, use_rewriting=True,
        )
        # Fallback: si el filter vacía resultados, reintentar sin filtro
        if not candidates and filter_dict is not None:
            candidates = self.hybrid.retrieve(
                query, top_k=RETRIEVAL_TOP_K, filter_dict=None, use_rewriting=True,
            )

        # 2) Re-ranking
        reranked = rerank_documents(query, candidates, top_k=top_k)

        # 3) Parent lookup (contexto más rico al LLM)
        final = resolve_parents(reranked)
        return final

    def search_as_documents(self, query: str, **kwargs) -> List[Document]:
        return [doc for doc, _ in self.search(query, **kwargs)]


# ==========================================
# Formateo para el prompt
# ==========================================
def format_context_for_prompt(ranked: List[Tuple[Document, float]]) -> str:
    """Genera el bloque [CONTEXTO] con citaciones explícitas."""
    if not ranked:
        return "(Sin contexto recuperado)"
    blocks = []
    for i, (doc, score) in enumerate(ranked, 1):
        src = doc.metadata.get("source", "N/A")
        src_name = src.split("/")[-1].split("\\")[-1] if src else "N/A"
        meta_bits = []
        if "unit" in doc.metadata:
            meta_bits.append(f"Unidad {doc.metadata['unit']}")
        if "level" in doc.metadata:
            meta_bits.append(f"Nivel {doc.metadata['level']}")
        if "topic" in doc.metadata:
            meta_bits.append(f"Tema: {doc.metadata['topic']}")
        meta_str = f" [{', '.join(meta_bits)}]" if meta_bits else ""
        # Usar original_content si existe (sin el prefix contextual)
        content = doc.metadata.get("original_content", doc.page_content)
        blocks.append(
            f"[Fragmento {i}] Fuente: {src_name}{meta_str} (score={score:.3f})\n{content}"
        )
    return "\n\n---\n\n".join(blocks)


def extract_citations(ranked: List[Tuple[Document, float]]) -> List[dict]:
    """Devuelve citaciones estructuradas (para render en UI)."""
    citations = []
    seen = set()
    for doc, score in ranked:
        src = doc.metadata.get("source", "N/A")
        src_name = src.split("/")[-1].split("\\")[-1] if src else "N/A"
        key = (src_name, doc.metadata.get("unit"), doc.metadata.get("page"))
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "source": src_name,
            "unit": doc.metadata.get("unit"),
            "level": doc.metadata.get("level"),
            "topic": doc.metadata.get("topic"),
            "page": doc.metadata.get("page"),
            "score": round(score, 4),
            "snippet": doc.metadata.get("original_content", doc.page_content)[:300],
            "full_text": doc.metadata.get("original_content", doc.page_content)[:2000],
        })
    return citations
