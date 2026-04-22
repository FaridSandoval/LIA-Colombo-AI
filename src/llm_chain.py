"""
Pipeline conversacional LIA-Colombo AI.

En vez del agente-con-tools original, hacemos un pipeline RAG explícito:
1. Guardrail de dominio.
2. AdvancedRetriever (hybrid + rewriting + rerank + parent lookup).
3. Guardrail de baja confianza.
4. Inyección de contexto + perfil del estudiante + historial.
5. LLM genera respuesta.
6. Devuelve (respuesta, citaciones, trace).

Esta arquitectura es más simple que agentic tool-calling y más fácil de
observar/medir (RAGAS, LangFuse, tests).
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_ollama import ChatOllama

from src.config import (
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    OLLAMA_BASE_URL,
    ENABLE_LANGFUSE,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from src.prompts import (
    TUTOR_SYSTEM_PROMPT,
    CONTEXT_INJECTION_TEMPLATE,
    LOW_CONFIDENCE_RESPONSE_TEMPLATE,
)
from src.guardrails import is_in_domain, detect_low_confidence
from src.retrieval import AdvancedRetriever, format_context_for_prompt, extract_citations

logger = logging.getLogger(__name__)


# ==========================================
# LangFuse (opcional)
# ==========================================
_langfuse_client = None
_langfuse_handler = None


def _get_langfuse():
    global _langfuse_client, _langfuse_handler
    if not ENABLE_LANGFUSE:
        return None, None
    if _langfuse_client is not None:
        return _langfuse_client, _langfuse_handler
    try:
        from langfuse import Langfuse
        from langfuse.callback import CallbackHandler
        _langfuse_client = Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        _langfuse_handler = CallbackHandler(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST,
        )
        logger.info("LangFuse inicializado.")
    except Exception as e:
        logger.warning(f"LangFuse no disponible: {e}")
        _langfuse_client = None
        _langfuse_handler = None
    return _langfuse_client, _langfuse_handler


# ==========================================
# Helpers
# ==========================================
def summarize_conversation_history(messages: List[dict], max_messages: int = 6) -> str:
    if not messages:
        return "(Sin historial previo)"
    recent = messages[-max_messages:]
    lines = []
    for m in recent:
        role = (m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")).upper()
        content = (m.get("content") if isinstance(m, dict) else getattr(m, "content", ""))
        lines.append(f"[{role}] {content[:250]}")
    return "\n".join(lines)


# ==========================================
# Resultado tipado
# ==========================================
@dataclass
class RAGResponse:
    answer: str
    citations: List[dict] = field(default_factory=list)
    retrieved_chunks: List[dict] = field(default_factory=list)
    guardrail_triggered: Optional[str] = None  # "off_domain" | "low_confidence" | None
    llm_model: str = ""
    trace_id: Optional[str] = None


# ==========================================
# Pipeline principal
# ==========================================
class LIARAGPipeline:
    def __init__(
        self,
        vector_store,
        llm_model: str = LLM_MODEL_NAME,
        temperature: float = LLM_TEMPERATURE,
    ):
        self.llm_model = llm_model
        self.llm = ChatOllama(
            model=llm_model.replace("ollama:", ""),
            base_url=OLLAMA_BASE_URL,
            temperature=temperature,
        )
        self.retriever = AdvancedRetriever(vector_store)
        self.langfuse_client, self.langfuse_handler = _get_langfuse()

    def _build_prompt(
        self,
        user_query: str,
        user_info: dict,
        conversation_history: List[dict],
        context_block: str,
    ) -> List[dict]:
        context_injection = CONTEXT_INJECTION_TEMPLATE.format(
            student_name=user_info.get("Student Name", "Estudiante"),
            student_course=user_info.get("Course", "Fundamental Plus"),
            student_status=user_info.get("Status", "Activo"),
            student_score=user_info.get("Final Score", "N/A"),
            teacher_feedback=user_info.get("Teacher Feedback", "(sin feedback previo)"),
            conversation_summary=summarize_conversation_history(conversation_history),
            retrieved_context=context_block,
        )
        return [
            {"role": "system", "content": TUTOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"{context_injection}\n\n**Pregunta del estudiante:** {user_query}"},
        ]

    def _infer_student_filters(self, user_info: dict) -> Dict[str, Any]:
        """Deriva level/unit del perfil del estudiante (si es posible)."""
        filters: Dict[str, Any] = {}
        course = (user_info.get("Course") or "").lower()
        # Heurística: si el Course menciona "A2", "B1", etc.
        import re
        m = re.search(r"\b([abc][12])\b", course)
        if m:
            filters["student_level"] = m.group(1).upper()
        # Unit si aparece
        m = re.search(r"unit[\s_-]?(\d+)", course)
        if m:
            filters["student_unit"] = int(m.group(1))
        return filters

    def query(
        self,
        user_query: str,
        user_info: Optional[dict] = None,
        conversation_history: Optional[List[dict]] = None,
    ) -> RAGResponse:
        user_info = user_info or {}
        conversation_history = conversation_history or []

        # --- 1. Guardrail de dominio ---
        if not is_in_domain(user_query):
            return RAGResponse(
                answer=(
                    "Esa pregunta parece estar fuera del ámbito de tu curso de inglés. "
                    "Estoy aquí para ayudarte con gramática, vocabulario, pronunciación "
                    "y práctica conversacional del ciclo Fundamental Plus. "
                    "¿Hay algún tema de la clase con el que pueda ayudarte?"
                ),
                guardrail_triggered="off_domain",
                llm_model=self.llm_model,
            )

        # --- 2. Retrieval avanzado ---
        filters = self._infer_student_filters(user_info)
        ranked = self.retriever.search(user_query, **filters)
        scores = [s for _, s in ranked]

        # --- 3. Guardrail de baja confianza ---
        if not ranked or detect_low_confidence(scores):
            return RAGResponse(
                answer=LOW_CONFIDENCE_RESPONSE_TEMPLATE.format(query=user_query),
                guardrail_triggered="low_confidence",
                retrieved_chunks=extract_citations(ranked),
                llm_model=self.llm_model,
            )

        # --- 4. Construir prompt y llamar al LLM ---
        context_block = format_context_for_prompt(ranked)
        messages = self._build_prompt(
            user_query, user_info, conversation_history, context_block,
        )

        callbacks = [self.langfuse_handler] if self.langfuse_handler else None
        trace_id = None
        try:
            response = self.llm.invoke(
                messages,
                config={"callbacks": callbacks} if callbacks else {},
            )
            answer = response.content
        except Exception as e:
            logger.error(f"Error invocando LLM: {e}")
            answer = "Lo siento, ocurrió un error técnico al generar la respuesta. Intenta de nuevo."

        citations = extract_citations(ranked)

        return RAGResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=citations,
            guardrail_triggered=None,
            llm_model=self.llm_model,
            trace_id=trace_id,
        )


# ==========================================
# Factory (compat con app.py previo)
# ==========================================
def get_pipeline(vector_store, llm_model: str = LLM_MODEL_NAME) -> LIARAGPipeline:
    return LIARAGPipeline(vector_store, llm_model=llm_model)


# Backward compat: algunos callers esperan un "agent executor"
def get_agent_executor(vector_store):
    """Shim de compatibilidad. Devuelve el pipeline nuevo."""
    return get_pipeline(vector_store)
