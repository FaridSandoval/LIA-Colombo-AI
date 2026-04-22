"""
LIA-Colombo AI — Streamlit app con RAG avanzado.
Incluye: citaciones, feedback 👍/👎, session memory persistente, filtros por perfil.
"""
import streamlit as st
import pandas as pd
from pathlib import Path

from src.document_loader import load_and_split_documents
from src.embeddings import create_or_load_vectorstore
from src.llm_chain import get_pipeline
from src.session_memory import (
    init_db, load_history, save_message, save_feedback, clear_history,
)
from src.config import LLM_MODEL_NAME, USER_DATA_DIR

st.set_page_config(page_title="LIA-Colombo AI Tutor", layout="wide", page_icon="🎓")

# ==========================================
# CACHE DE RECURSOS
# ==========================================
@st.cache_resource
def get_vectorstore():
    return create_or_load_vectorstore()


@st.cache_resource
def get_rag_pipeline(llm_model: str):
    vs = get_vectorstore()
    return get_pipeline(vs, llm_model=llm_model)


# ==========================================
# HELPERS
# ==========================================
def get_user_data(id_number: str):
    file_path = USER_DATA_DIR / "estudiantes_dummies.xlsx"
    if not file_path.exists():
        return None
    df = pd.read_excel(file_path)
    row = df[df["ID Number"].astype(str) == str(id_number)]
    return row.iloc[0].to_dict() if not row.empty else None


def render_citations(citations: list):
    if not citations:
        return
    with st.expander(f"📚 Fuentes consultadas ({len(citations)})"):
        for i, c in enumerate(citations, 1):
            meta_bits = []
            if c.get("unit") is not None:
                meta_bits.append(f"Unidad {c['unit']}")
            if c.get("level"):
                meta_bits.append(f"Nivel {c['level']}")
            if c.get("topic"):
                meta_bits.append(f"Tema: {c['topic']}")
            if c.get("page") is not None:
                meta_bits.append(f"Página {c['page']}")
            meta_str = " · ".join(meta_bits)
            st.markdown(f"**{i}. {c['source']}** — {meta_str}  · _score: {c['score']}_")
            st.caption(c["snippet"])


# ==========================================
# ESTADO
# ==========================================
init_db()

for key, default in [
    ("logged_in", False),
    ("user_info", None),
    ("messages", []),
    ("selected_llm", LLM_MODEL_NAME),
    ("last_rag_response", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# LOGIN
# ==========================================
if not st.session_state.logged_in or st.session_state.user_info is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 LIA-Colombo AI Login")
        st.subheader("Plataforma de Tutoría Inteligente")
        with st.form("login_form"):
            id_input = st.text_input("Ingrese su ID Number")
            if st.form_submit_button("Ingresar"):
                user_data = get_user_data(id_input)
                if user_data:
                    st.session_state.user_info = user_data
                    st.session_state.logged_in = True
                    # Cargar historial persistente
                    history = load_history(str(id_input))
                    st.session_state.messages = [
                        {"role": h["role"], "content": h["content"]} for h in history
                    ]
                    st.rerun()
                else:
                    st.error("ID no encontrado. Verifique los datos.")
    st.stop()

user_info = st.session_state.user_info
student_id = str(user_info.get("ID Number", "anon"))

st.title(f"🤖 Tutor IA — Hola, {user_info['Student Name']}")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    is_admin = user_info.get("Student Name", "").lower() == "admin"

    if is_admin:
        st.header("👤 Admin")
        st.info("**Rol:** Administrador")
        st.divider()

        st.header("⚙️ Gestión de Documentos")
        if st.button("🔄 Re-indexar Base de Conocimiento"):
            with st.spinner("Indexando (parent-child + contextual)..."):
                docs = load_and_split_documents()
                create_or_load_vectorstore(docs)
                st.cache_resource.clear()
                st.success(f"✅ {len(docs)} chunks indexados.")

        st.divider()
        st.header("🧪 Modelo LLM")
        from src.config import LLM_BENCHMARK_CANDIDATES
        candidates = [LLM_MODEL_NAME] + [
            m for m in LLM_BENCHMARK_CANDIDATES if m != LLM_MODEL_NAME
        ]
        selected = st.selectbox("Elegir modelo", candidates,
                                index=candidates.index(st.session_state.selected_llm)
                                if st.session_state.selected_llm in candidates else 0)
        if selected != st.session_state.selected_llm:
            st.session_state.selected_llm = selected
            st.cache_resource.clear()
            st.info(f"Modelo actualizado a **{selected}**. Próxima pregunta usará este modelo.")
    else:
        st.header("👤 Perfil del Estudiante")
        st.info(
            f"**Curso:** {user_info['Course']}\n\n"
            f"**Estado:** {user_info['Status']}\n\n"
            f"**Nota:** {user_info['Final Score']}"
        )
        with st.expander("📝 Feedback del Profesor"):
            st.caption(user_info["Teacher Feedback"])

    st.divider()
    if st.button("🧹 Limpiar conversación"):
        clear_history(student_id)
        st.session_state.messages = []
        st.rerun()
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.session_state.messages = []
        st.rerun()

# ==========================================
# CHAT
# ==========================================
for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("citations"):
            render_citations(message["citations"])
        # Botones de feedback sólo en el último mensaje del asistente
        if (
            message["role"] == "assistant"
            and i == len(st.session_state.messages) - 1
            and not message.get("feedback_given")
        ):
            c1, c2, _ = st.columns([1, 1, 10])
            with c1:
                if st.button("👍", key=f"up_{i}"):
                    save_feedback(
                        student_id,
                        query=st.session_state.messages[i - 1]["content"] if i > 0 else "",
                        response=message["content"],
                        rating=1,
                        llm_model=message.get("llm_model", ""),
                        citations=message.get("citations"),
                    )
                    st.session_state.messages[i]["feedback_given"] = True
                    st.rerun()
            with c2:
                if st.button("👎", key=f"down_{i}"):
                    save_feedback(
                        student_id,
                        query=st.session_state.messages[i - 1]["content"] if i > 0 else "",
                        response=message["content"],
                        rating=-1,
                        llm_model=message.get("llm_model", ""),
                        citations=message.get("citations"),
                    )
                    st.session_state.messages[i]["feedback_given"] = True
                    st.rerun()

# Input
if prompt := st.chat_input("Escribe tu duda sobre la clase..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(student_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    pipeline = get_rag_pipeline(st.session_state.selected_llm)

    with st.chat_message("assistant"):
        with st.spinner("Consultando tus materiales de clase..."):
            rag_response = pipeline.query(
                user_query=prompt,
                user_info=user_info,
                conversation_history=st.session_state.messages[:-1],
            )

        st.markdown(rag_response.answer)
        if rag_response.guardrail_triggered == "off_domain":
            st.info("🛡️ Guardrail: pregunta fuera de dominio.")
        elif rag_response.guardrail_triggered == "low_confidence":
            st.warning("🛡️ Guardrail: baja confianza en el material recuperado.")
        render_citations(rag_response.citations)

    msg = {
        "role": "assistant",
        "content": rag_response.answer,
        "citations": rag_response.citations,
        "llm_model": rag_response.llm_model,
        "guardrail": rag_response.guardrail_triggered,
    }
    st.session_state.messages.append(msg)
    save_message(student_id, "assistant", rag_response.answer)
    st.rerun()
