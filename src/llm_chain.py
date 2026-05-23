"""
Pipeline conversacional LIA-Colombo AI — arquitectura agentic tool-calling.

El LLM decide cuándo y si invocar:
  - retrieve_context(): búsqueda híbrida en el corpus solo cuando lo necesita.
  - check_grammar(): corrección gramatical solo cuando detecta errores.

Sin middleware que fuerce retrieval en cada turno. Sin doble retrieval.
"""
from __future__ import annotations
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from src.config import (
    LLM_MODEL_NAME,
    LLM_TEMPERATURE,
    OPENAI_API_KEY,
    ENABLE_LANGFUSE,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from src.prompts import (
    TUTOR_SYSTEM_PROMPT,
    GRAMMAR_CHECK_PROMPT,
)
from src.guardrails import is_in_domain
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
def summarize_conversation_history(messages: List[dict], max_messages: int = 20) -> str:
    if not messages:
        return "(Sin historial previo)"
    recent = messages[-max_messages:]
    lines = []
    for m in recent:
        role = (m.get("role") if isinstance(m, dict) else getattr(m, "type", "user")).upper()
        content = (m.get("content") if isinstance(m, dict) else getattr(m, "content", ""))
        lines.append(f"[{role}] {content[:300]}")
    return "\n".join(lines)


def _infer_student_filters(user_info: dict) -> Dict[str, Any]:
    """Deriva level/unit del perfil del estudiante (si es posible)."""
    filters: Dict[str, Any] = {}
    course = (user_info.get("Course") or "").lower()
    m = re.search(r"\b([abc][12])\b", course)
    if m:
        filters["student_level"] = m.group(1).upper()
    m = re.search(r"unit[\s_-]?(\d+)", course)
    if m:
        filters["student_unit"] = int(m.group(1))
    return filters


# ==========================================
# Resultado tipado
# ==========================================
@dataclass
class RAGResponse:
    answer: str
    citations: List[dict] = field(default_factory=list)
    retrieved_chunks: List[dict] = field(default_factory=list)
    guardrail_triggered: Optional[str] = None  # "off_domain" | None
    llm_model: str = ""
    trace_id: Optional[str] = None


# ==========================================
# Pipeline agentic tool-calling
# ==========================================
class LIAAgentPipeline:
    """
    El LLM invoca retrieve_context() y check_grammar() como tools solo
    cuando lo necesita. Sin retrieval forzado, sin doble retrieval.
    """

    MAX_TOOL_ROUNDS = 3

    def __init__(
        self,
        vector_store,
        llm_model: str = LLM_MODEL_NAME,
        temperature: float = LLM_TEMPERATURE,
    ):
        self.llm_model = llm_model
        self._base_llm = ChatOpenAI(
            model=llm_model,
            api_key=OPENAI_API_KEY,
            temperature=temperature,
            streaming=True,
        )
        self.retriever = AdvancedRetriever(vector_store)
        self.langfuse_client, self.langfuse_handler = _get_langfuse()

    def _make_tools(self, user_info: dict, citations_bucket: List[dict]) -> list:
        """Crea las tools con closures sobre el retriever, filtros y bucket de citas."""
        retriever = self.retriever
        filters = _infer_student_filters(user_info)

        @tool
        def retrieve_context(query: str) -> str:
            """Search the English course corpus (textbooks, grammar rules, exercises) for content relevant to the student's question. Call this when the student asks about specific grammar rules, vocabulary, exercises, or needs course-specific material. Do NOT call for simple conversational exchanges or greetings."""
            ranked = retriever.search(query, **filters)
            if not ranked:
                return "(No relevant content found in course materials. Use your general English teaching knowledge.)"
            citations_bucket.extend(extract_citations(ranked))
            return format_context_for_prompt(ranked)

        @tool
        def check_grammar(text: str) -> str:
            """Check the student's English text for grammar or spelling errors. Returns the corrected sentence, or 'OK' if the text is correct. Call this whenever the student writes something in English that may contain errors."""
            import os as _os
            from openai import OpenAI as _OpenAI
            client = _OpenAI(api_key=_os.getenv("OPENAI_API_KEY"))
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": GRAMMAR_CHECK_PROMPT.format(text=text)}],
                max_tokens=100,
                temperature=0,
            )
            return resp.choices[0].message.content.strip()

        return [retrieve_context, check_grammar]

    def _build_messages(
        self,
        user_query: str,
        user_info: dict,
        conversation_history: List[dict],
    ) -> list:
        student_profile = (
            f"Nombre: {user_info.get('Student Name', 'Estudiante')}\n"
            f"Curso / Nivel: {user_info.get('Course', 'Fundamental Plus')}\n"
            f"Estado: {user_info.get('Status', 'Activo')}\n"
            f"Nota actual: {user_info.get('Final Score', 'N/A')}\n"
            f"Feedback del profesor: {user_info.get('Teacher Feedback', '(sin feedback previo)')}"
        )
        history_summary = summarize_conversation_history(conversation_history)
        system_content = (
            TUTOR_SYSTEM_PROMPT
            + f"\n\n[PERFIL DEL ESTUDIANTE]\n{student_profile}"
            + f"\n\n[HISTORIAL RESUMIDO DE LA CONVERSACIÓN]\n{history_summary}"
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=user_query),
        ]

    def query_stream(
        self,
        user_query: str,
        user_info: Optional[dict] = None,
        conversation_history: Optional[List[dict]] = None,
    ):
        """
        Agentic query_stream. Devuelve (generator, citations, guardrail).
        El generator yield-ea texto para streaming en Streamlit.
        """
        user_info = user_info or {}
        conversation_history = conversation_history or []

        # Guardrail de dominio (pre-check rápido)
        if not is_in_domain(user_query):
            def _off():
                yield (
                    "That question is outside my English class scope. "
                    "I'm here to help with grammar, vocabulary, pronunciation "
                    "and conversation practice! What English topic can I help you with? 😊"
                )
            return _off(), [], "off_domain"

        citations_bucket: List[dict] = []
        tools = self._make_tools(user_info, citations_bucket)
        llm_with_tools = self._base_llm.bind_tools(tools)
        tool_map = {t.name: t for t in tools}

        messages = self._build_messages(user_query, user_info, conversation_history)
        callbacks_cfg = {"callbacks": [self.langfuse_handler]} if self.langfuse_handler else {}

        # Loop agentic (máx MAX_TOOL_ROUNDS rondas de tool-calling)
        for _round in range(self.MAX_TOOL_ROUNDS):
            ai_msg = llm_with_tools.invoke(messages, config=callbacks_cfg)

            if not getattr(ai_msg, "tool_calls", None):
                # El LLM respondió directamente sin invocar tools
                final_text = ai_msg.content or ""
                def _yield(t=final_text):
                    yield t
                return _yield(), citations_bucket, None

            # Ejecutar todas las tool calls de esta ronda
            messages.append(ai_msg)
            for tc in ai_msg.tool_calls:
                fn = tool_map.get(tc["name"])
                try:
                    result = fn.invoke(tc["args"]) if fn else "Tool not found."
                except Exception as e:
                    logger.warning(f"Tool '{tc['name']}' falló: {e}")
                    result = f"Tool error: {e}"
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        # Tras MAX_TOOL_ROUNDS, stream la respuesta final (sin binding de tools)
        def _stream_final(msgs=messages):
            for chunk in self._base_llm.stream(msgs, config=callbacks_cfg):
                yield chunk.content if hasattr(chunk, "content") else str(chunk)

        return _stream_final(), citations_bucket, None

    def query(
        self,
        user_query: str,
        user_info: Optional[dict] = None,
        conversation_history: Optional[List[dict]] = None,
    ) -> RAGResponse:
        gen, citations, guardrail = self.query_stream(user_query, user_info, conversation_history)
        answer = "".join(gen)
        return RAGResponse(
            answer=answer,
            citations=citations,
            retrieved_chunks=citations,
            guardrail_triggered=guardrail,
            llm_model=self.llm_model,
        )


# Alias para compat con cualquier import de LIARAGPipeline
LIARAGPipeline = LIAAgentPipeline


# ==========================================
# Factory
# ==========================================
def get_pipeline(vector_store, llm_model: str = LLM_MODEL_NAME) -> LIAAgentPipeline:
    return LIAAgentPipeline(vector_store, llm_model=llm_model)


def get_agent_executor(vector_store):
    """Backward compat."""
    return get_pipeline(vector_store)
