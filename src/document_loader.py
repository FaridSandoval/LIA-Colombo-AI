"""
Document loader con:
- Chunking Parent-Child (small-to-big).
- Metadata estructural por unidad/nivel/tema (desde XLSX de syllabus).
- Contextual Retrieval (Anthropic, sep 2024) con cache en disco.
"""
from __future__ import annotations
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Tuple
import yaml

import pandas as pd
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    DirectoryLoader, PyPDFLoader, TextLoader,
)
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import (
    RAW_DATA_DIR,
    PARENT_DOCS_DIR,
    CONTEXTUAL_CACHE_DIR,
    PARENT_CHUNK_SIZE,
    PARENT_CHUNK_OVERLAP,
    CHILD_CHUNK_SIZE,
    CHILD_CHUNK_OVERLAP,
    CHUNK_SEPARATORS,
    ENABLE_CONTEXTUAL_RETRIEVAL,
    CONTEXTUAL_MAX_WORDS,
    OLLAMA_BASE_URL,
    LLM_UTILITY_MODEL,
)
from src.prompts import CONTEXTUAL_CHUNK_PROMPT

logger = logging.getLogger(__name__)

EXCLUDED_DIRS = {"quarantine"}
ALLOWED_ROOT_FILES = {"syllabus.xlsx"}

# Filtro de calidad para fuentes con OCR ruidoso
MIN_USEFUL_CHARS_PER_PAGE = 100      # páginas con menos texto se descartan
MAX_NOISE_RATIO = 0.30                # más de 30% caracteres no alfabéticos = página ruido
QUALITY_FILTERED_SOURCES = {"student_book"}  # source_types donde aplicar el filtro


# ==========================================
# Helpers
# ==========================================
def _hash_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _load_contextual_cache() -> dict:
    cache_file = CONTEXTUAL_CACHE_DIR / "context_cache.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_contextual_cache(cache: dict) -> None:
    cache_file = CONTEXTUAL_CACHE_DIR / "context_cache.json"
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _infer_unit_metadata(file_path: str) -> dict:
    """Extrae unidad/nivel del nombre de archivo si sigue la convención."""
    name = Path(file_path).stem.lower()
    meta = {}
    # Patrones: "fundamental_plus_unit3", "unidad_2", "level_a2", "book1_u5"
    import re
    m = re.search(r"u(?:nit|nidad)?[_\s-]?(\d+)", name)
    if m:
        meta["unit"] = int(m.group(1))
    m = re.search(r"(?:level|nivel)[_\s-]?([a-zA-Z]\d)", name)
    if m:
        meta["level"] = m.group(1).upper()
    if "fundamental" in name:
        meta["program"] = "fundamental_plus"
    return meta


def _is_excluded(path: Path) -> bool:
    """True si el path está dentro de una subcarpeta excluida."""
    rel = path.relative_to(RAW_DATA_DIR)
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def _infer_source_type(file_path: Path) -> str:
    """Devuelve el nombre de la subcarpeta dentro de data/raw/ como source_type."""
    rel = file_path.relative_to(RAW_DATA_DIR)
    if len(rel.parts) < 2:
        raise ValueError(f"Archivo {file_path.name} en raíz no debería indexarse")
    return rel.parts[0]


def _is_low_quality_text(text: str) -> tuple[bool, str]:
    """
    Evalúa si un texto tiene calidad suficiente para indexar.
    Devuelve (es_baja_calidad, razón).
    """
    text = text.strip()
    n_chars = len(text)
    if n_chars < MIN_USEFUL_CHARS_PER_PAGE:
        return True, f"too_short({n_chars}c)"

    # Ratio de caracteres alfabéticos vs total
    n_alpha = sum(1 for c in text if c.isalpha() or c.isspace())
    alpha_ratio = n_alpha / max(n_chars, 1)
    if alpha_ratio < (1 - MAX_NOISE_RATIO):
        return True, f"too_noisy(alpha_ratio={alpha_ratio:.2f})"

    return False, ""


def _validate_no_orphan_files_in_root() -> None:
    """Falla si hay archivos en data/raw/ raíz que no estén en ALLOWED_ROOT_FILES."""
    orphans = []
    for item in RAW_DATA_DIR.iterdir():
        if item.is_file() and item.name not in ALLOWED_ROOT_FILES:
            orphans.append(item.name)
    if orphans:
        raise ValueError(
            f"Archivos no clasificados en data/raw/: {orphans}. "
            f"Movelos a una subcarpeta (book_te/, supplementary/, vocabulary/, "
            f"student_book/) o agregalos a ALLOWED_ROOT_FILES si son metadata estructural."
        )


# ==========================================
# Excel estructurado (syllabus)
# ==========================================
def process_excel_by_rows(file_path) -> List[Document]:
    """
    Procesa Excel: 1 fila = 1 Document con metadatos estructurales.
    Detecta columnas candidatas: unit/unidad, level/nivel, topic/tema.
    """
    df = pd.read_excel(file_path)
    # Normalizar nombres de columnas
    col_map = {c.lower().strip(): c for c in df.columns}
    unit_col = next((col_map[k] for k in ["unit", "unidad"] if k in col_map), None)
    level_col = next((col_map[k] for k in ["level", "nivel"] if k in col_map), None)
    topic_col = next((col_map[k] for k in ["topic", "tema", "subject"] if k in col_map), None)

    docs = []
    for idx, row in df.iterrows():
        content = " | ".join(
            f"{col}: {val}" for col, val in row.items() if pd.notna(val)
        )
        metadata = {
            "source": str(file_path),
            "row": int(idx),
            "type": "structured",
            "source_type": "syllabus",
        }
        if unit_col and pd.notna(row[unit_col]):
            try:
                metadata["unit"] = int(row[unit_col])
            except (ValueError, TypeError):
                metadata["unit"] = str(row[unit_col])
        if level_col and pd.notna(row[level_col]):
            metadata["level"] = str(row[level_col]).upper()
        if topic_col and pd.notna(row[topic_col]):
            metadata["topic"] = str(row[topic_col])

        docs.append(Document(page_content=content, metadata=metadata))
    return docs


# ==========================================
# Text files (PDF/TXT/MD) → parent + child
# ==========================================
def _load_text_documents() -> List[Document]:
    """Carga PDF/TXT desde RAW_DATA_DIR recursivamente; excluye EXCLUDED_DIRS."""
    extensions = {
        "**/*.pdf": PyPDFLoader,
        "**/*.txt": TextLoader,
    }
    docs = []
    for glob_pattern, loader_cls in extensions.items():
        loader = DirectoryLoader(
            str(RAW_DATA_DIR), glob=glob_pattern, loader_cls=loader_cls,
            recursive=True,
        )
        try:
            loaded = loader.load()
        except Exception as e:
            logger.warning(f"Error cargando {glob_pattern}: {e}")
            loaded = []
        filtered_count = 0
        for d in loaded:
            src = Path(d.metadata.get("source", ""))
            if _is_excluded(src):
                continue
            d.metadata.update(_infer_unit_metadata(str(src)))
            source_type = _infer_source_type(src)
            d.metadata["source_type"] = source_type

            # Filtro de calidad para fuentes con OCR ruidoso
            if source_type in QUALITY_FILTERED_SOURCES:
                is_bad, reason = _is_low_quality_text(d.page_content)
                if is_bad:
                    filtered_count += 1
                    logger.debug(f"Filtrada página de {src.name} (page={d.metadata.get('page', '?')}): {reason}")
                    continue
            docs.append(d)

        if filtered_count:
            logger.info(f"Filtro de calidad: {filtered_count} páginas descartadas por baja calidad/ruido OCR.")

    for md_file in sorted(RAW_DATA_DIR.rglob("*.md")):
        if _is_excluded(md_file):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
            metadata = {"source": str(md_file), "source_type": _infer_source_type(md_file)}
            if text.startswith("---"):
                end_idx = text.find("\n---", 3)
                if end_idx != -1:
                    fm_raw = text[3:end_idx]
                    body = text[end_idx + 4:].lstrip("\n")
                    try:
                        fm = yaml.safe_load(fm_raw) or {}
                        for k, v in fm.items():
                            metadata[k] = ", ".join(v) if isinstance(v, list) else v
                    except Exception as yaml_err:
                        logger.warning(f"Frontmatter YAML inválido en {md_file.name}: {yaml_err}")
                        body = text
                        metadata.update(_infer_unit_metadata(str(md_file)))
                else:
                    body = text
                    metadata.update(_infer_unit_metadata(str(md_file)))
            else:
                body = text
                metadata.update(_infer_unit_metadata(str(md_file)))
            source_type = _infer_source_type(md_file)
            if source_type in QUALITY_FILTERED_SOURCES:
                is_bad, reason = _is_low_quality_text(body)
                if is_bad:
                    logger.debug(f"Filtrado .md de baja calidad {md_file.name}: {reason}")
                    continue
            docs.append(Document(page_content=body, metadata=metadata))
        except Exception as e:
            logger.warning(f"Error cargando {md_file.name}: {e}")
    return docs


def _split_parent_child(docs: List[Document]) -> Tuple[List[Document], List[Document]]:
    """Genera parents (1500-2000c) y children (300-400c) con vínculo por parent_id."""
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
    )

    parents: List[Document] = []
    children: List[Document] = []

    for doc in docs:
        parent_chunks = parent_splitter.split_documents([doc])
        for parent in parent_chunks:
            parent_id = _hash_text(parent.page_content)
            parent.metadata["parent_id"] = parent_id
            parents.append(parent)

            for child in child_splitter.split_documents([parent]):
                child.metadata = {**parent.metadata, **child.metadata}
                child.metadata["parent_id"] = parent_id
                children.append(child)
    return parents, children


def _persist_parents(parents: List[Document]) -> None:
    """Guarda parents en disco (JSONL) para lookup por parent_id."""
    store_file = PARENT_DOCS_DIR / "parents.jsonl"
    with store_file.open("w", encoding="utf-8") as f:
        for p in parents:
            f.write(json.dumps({
                "parent_id": p.metadata["parent_id"],
                "content": p.page_content,
                "metadata": p.metadata,
            }, ensure_ascii=False) + "\n")


def load_parent_store() -> dict:
    """Carga parents persistidos como {parent_id: Document}."""
    store_file = PARENT_DOCS_DIR / "parents.jsonl"
    store = {}
    if not store_file.exists():
        return store
    with store_file.open("r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            store[data["parent_id"]] = Document(
                page_content=data["content"], metadata=data["metadata"]
            )
    return store


# ==========================================
# Contextual Retrieval (Anthropic)
# ==========================================
def _get_utility_llm():
    try:
        from langchain_openai import ChatOpenAI
        from src.config import OPENAI_API_KEY
        return ChatOpenAI(model=LLM_UTILITY_MODEL, api_key=OPENAI_API_KEY, temperature=0.0)
    except Exception as e:
        logger.warning(f"No se pudo iniciar utility LLM: {e}")
        return None


def contextualize_chunks(
    children: List[Document],
    parents_by_id: dict,
    llm=None,
) -> List[Document]:
    """
    Anthropic Contextual Retrieval: prepend un resumen de 50 palabras a cada child.
    Se hace una sola vez en indexación. Resultados cacheados en disco.
    """
    if not ENABLE_CONTEXTUAL_RETRIEVAL:
        return children

    if llm is None:
        llm = _get_utility_llm()
    if llm is None:
        logger.warning("Skip contextual retrieval — LLM utilitario no disponible.")
        return children

    cache = _load_contextual_cache()
    enriched: List[Document] = []
    new_entries = 0

    for child in children:
        chunk_hash = _hash_text(child.page_content)
        parent_id = child.metadata.get("parent_id")
        parent = parents_by_id.get(parent_id)

        if chunk_hash in cache:
            context_note = cache[chunk_hash]
        elif parent is None:
            context_note = ""
        else:
            # Truncar documento-parent para evitar contexto excesivo
            doc_text = parent.page_content[:3000]
            prompt = CONTEXTUAL_CHUNK_PROMPT.format(
                max_words=CONTEXTUAL_MAX_WORDS,
                document=doc_text,
                chunk=child.page_content,
            )
            try:
                context_note = llm.invoke(prompt).content.strip()
            except Exception as e:
                logger.warning(f"Contextualización falló en chunk {chunk_hash}: {e}")
                context_note = ""
            cache[chunk_hash] = context_note
            new_entries += 1

        if context_note:
            new_content = f"{context_note}\n\n{child.page_content}"
        else:
            new_content = child.page_content

        enriched.append(Document(
            page_content=new_content,
            metadata={**child.metadata, "original_content": child.page_content},
        ))

    if new_entries:
        _save_contextual_cache(cache)
        logger.info(f"Contextualización: {new_entries} chunks nuevos cacheados.")
    return enriched


# ==========================================
# API PÚBLICA
# ==========================================
def load_and_split_documents() -> List[Document]:
    """
    Pipeline completo de indexación:
    1. Valida que no haya archivos huérfanos en data/raw/ raíz.
    2. Carga PDFs/TXT/MD recursivamente → splits parent + child con metadata estructural.
    3. Carga XLSX (excluye ALLOWED_ROOT_FILES y quarantine) → 1 fila = 1 Document.
    4. Aplica contextual retrieval a los children.
    5. Persiste parents para ParentDocumentRetriever.
    Devuelve sólo los CHILDREN (que son los que se embedean).
    """
    _validate_no_orphan_files_in_root()

    final_children: List[Document] = []
    all_parents: List[Document] = []

    # 1) Text sources → parent/child
    text_docs = _load_text_documents()
    if text_docs:
        parents, children = _split_parent_child(text_docs)
        all_parents.extend(parents)
        final_children.extend(children)

    # 2) Excel (excluye syllabus de raíz y subcarpetas excluidas)
    excel_files = list(RAW_DATA_DIR.rglob("*.xlsx"))
    for file in excel_files:
        if _is_excluded(file) or file.name in ALLOWED_ROOT_FILES:
            logger.info(f"Skipping {file.name} (metadata estructural, no se indexa)")
            continue
        excel_docs = process_excel_by_rows(file)
        for d in excel_docs:
            pid = _hash_text(d.page_content)
            d.metadata["parent_id"] = pid
            all_parents.append(d)
            final_children.append(d)

    # 3) Persistir parents
    if all_parents:
        _persist_parents(all_parents)

    # 4) Contextual Retrieval
    if final_children:
        parents_by_id = {p.metadata["parent_id"]: p for p in all_parents}
        final_children = contextualize_chunks(final_children, parents_by_id)

    logger.info(
        f"Indexación: {len(all_parents)} parents, {len(final_children)} children."
    )
    return final_children
