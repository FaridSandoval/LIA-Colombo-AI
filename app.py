"""
LIA-Colombo AI — Streamlit app con RAG avanzado.
Incluye: citaciones, feedback 👍/👎, session memory persistente, filtros por perfil.
"""
import hashlib
import os
import streamlit as st
import pandas as pd
from pathlib import Path
from openai import OpenAI

from src.document_loader import load_and_split_documents
from src.embeddings import create_or_load_vectorstore
from src.llm_chain import get_pipeline
from src.session_memory import (
    init_db, load_history, save_message, save_feedback, clear_history,
)
from src.config import LLM_MODEL_NAME, USER_DATA_DIR

st.set_page_config(page_title="LIA-Colombo AI Tutor", layout="wide", page_icon="🇨🇴")

st.markdown("""
<style>
/* Sidebar institucional */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A2744 0%, #0D1B3E 100%);
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stButton > button {
    background-color: #FFD94F;
    color: #1A2744;
    border: none;
    border-radius: 8px;
    font-weight: 700;
    width: 100%;
    margin-bottom: 4px;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #EB8E35;
    color: white;
}

/* Header con línea amarilla */
h1 { border-bottom: 4px solid #FFD94F; padding-bottom: 8px; }

/* Botones principales */
.stButton > button {
    background-color: #FFD94F;
    color: #1A2744;
    border: none;
    border-radius: 8px;
    font-weight: 700;
}
.stButton > button:hover {
    background-color: #EB8E35;
    color: white;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    border: 2px solid #FFD94F !important;
    border-radius: 12px !important;
}

/* Burbujas del asistente */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background-color: #F0F7FF;
    border-left: 4px solid #04A6E1;
    border-radius: 0 12px 12px 0;
}

/* Expander fuentes */
[data-testid="stExpander"] {
    border: 1px solid #04A6E1 !important;
    border-radius: 8px;
}

/* Info/warning/success */
[data-testid="stAlert"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

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


def strip_sources_block(answer: str) -> str:
    """Elimina el bloque '📚 Fuentes:' que genera el LLM del texto de respuesta."""
    import re
    cleaned = re.sub(r'\n*📚\s*Fuentes:.*', '', answer, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def detect_translation_request(text: str) -> bool:
    """Detecta si el estudiante pide traducción o dice que no entendió."""
    import re
    patterns = [
        r"no entend[ií]", r"no comprendo", r"trad[uú]ce", r"en espa[ñn]ol",
        r"no te entiendo", r"qu[eé] significa", r"no s[eé] qu[eé] dijiste",
        r"puedes explicar", r"explain.*spanish", r"i don.t understand",
    ]
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio usando OpenAI Whisper."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=("audio.wav", audio_bytes, "audio/wav"),
        language="en",
    )
    return transcript.text


def generate_speech(text: str) -> bytes:
    """Genera audio de la respuesta de LIA usando OpenAI TTS."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    import re
    clean = re.sub(r'\*+', '', text)
    clean = re.sub(r'📚.*', '', clean, flags=re.DOTALL).strip()
    clean = clean[:4000]
    response = client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=clean,
    )
    return response.content


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
    ("pending_prompt", None),
    ("last_audio_hash", None),
    ("last_prompt_was_audio", False),
    ("tts_audio_bytes", None),
    ("pending_audio_bytes", None),
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

# Lógica para extraer el primer nombre de pila (asumiendo APELLIDO APELLIDO NOMBRE)
nombre_completo = user_info.get('Student Name', 'Estudiante')
partes_nombre = nombre_completo.split()

# Si tiene 3 o más palabras, tomamos la tercera (el nombre). Si no, tomamos la primera.
if len(partes_nombre) >= 3:
    primer_nombre_pila = partes_nombre[2].title()
else:
    primer_nombre_pila = partes_nombre[0].title()

st.title(f"🤖 LIA — Hola, {primer_nombre_pila}")

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.image("assets/colombo_logo_transparent.png", use_container_width=True)
    st.divider()
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
        if message["role"] == "user" and message.get("audio_bytes"):
            st.audio(message["audio_bytes"], format="audio/wav")
        if message["role"] == "assistant" and message.get("tts_audio_bytes"):
            st.audio(message["tts_audio_bytes"], format="audio/mp3")
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

# Mensaje de bienvenida cuando el chat está vacío
if not st.session_state.messages:
    with st.chat_message("assistant"):
        st.markdown(f"Hi, **{primer_nombre_pila}**! 👋 I'm **LIA**, your English tutor from Colombo.\n\nWhat do you want to do today?")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("📖 Question about my book", key="opt1", use_container_width=True):
                st.session_state.pending_prompt = "I have a question about my book"
                st.rerun()
            if st.button("📝 Explain a grammar topic", key="opt3", use_container_width=True):
                st.session_state.pending_prompt = "Can you explain a grammar topic?"
                st.rerun()
        with col2:
            if st.button("💬 Practice conversation", key="opt2", use_container_width=True):
                st.session_state.pending_prompt = "I want to practice conversation in English"
                st.rerun()
            if st.button("✏️ Check my writing", key="opt4", use_container_width=True):
                st.session_state.pending_prompt = "Can you check my writing?"
                st.rerun()

        if st.button("🔍 Something else — I'll type my question", key="opt5", use_container_width=True):
            pass  # El usuario simplemente escribe en el chat input

# Reproducir audio TTS si hay uno pendiente del turno anterior
if st.session_state.tts_audio_bytes is not None:
    import base64
    audio_b64 = base64.b64encode(st.session_state.tts_audio_bytes).decode()
    st.markdown(
        f'<audio autoplay><source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3"></audio>',
        unsafe_allow_html=True,
    )
    st.session_state.tts_audio_bytes = None

# ── Feature: Grabación de audio ──
with st.expander("🎤 Practice Speaking — tap to record"):
    audio_data = st.audio_input("Record your question in English")
    if audio_data is not None:
        audio_bytes = audio_data.read()
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if st.session_state.last_audio_hash != audio_hash:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Transcribing your audio... 🎧"):
                try:
                    transcribed = transcribe_audio(audio_bytes)
                    st.success(f"You said: _{transcribed}_")
                    st.session_state.pending_prompt = transcribed
                    st.session_state.last_prompt_was_audio = True
                    st.session_state.pending_audio_bytes = audio_bytes
                    st.rerun()
                except Exception as e:
                    st.error(f"Transcription error: {e}")

# Input
_chat_input = st.chat_input("Escribe tu duda sobre la clase...")
prompt = st.session_state.pending_prompt or _chat_input
if st.session_state.pending_prompt:
    st.session_state.pending_prompt = None
if prompt:
    user_msg = {"role": "user", "content": prompt}
    if st.session_state.pending_audio_bytes is not None:
        user_msg["audio_bytes"] = st.session_state.pending_audio_bytes
        st.session_state.pending_audio_bytes = None
    st.session_state.messages.append(user_msg)
    save_message(student_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    pipeline = get_rag_pipeline(st.session_state.selected_llm)

    try:
        with st.chat_message("assistant"):
            with st.spinner("Consultando tus materiales de clase..."):
                _query = prompt
                if detect_translation_request(prompt):
                    _query = (
                        "⚠️ INSTRUCCIÓN OBLIGATORIA: El estudiante no entendió tu respuesta anterior. "
                        "Debes responder TODO en español simple y claro. "
                        "Explica lo que dijiste antes en español. "
                        "Al final agrega exactamente: 'Now you try! 💪'\n\n"
                        f"Mensaje del estudiante: {prompt}"
                    )
                rag_response = pipeline.query(
                    user_query=_query,
                    user_info=user_info,
                    conversation_history=st.session_state.messages[:-1],
                )

            st.markdown(strip_sources_block(rag_response.answer))
            tts_audio_for_msg = None
            if st.session_state.last_prompt_was_audio:
                st.session_state.last_prompt_was_audio = False
                try:
                    audio_response = generate_speech(rag_response.answer)
                    st.session_state.tts_audio_bytes = audio_response
                    tts_audio_for_msg = audio_response
                except Exception as tts_err:
                    st.error(f"TTS error: {tts_err}")
            if rag_response.guardrail_triggered == "off_domain":
                st.info("🛡️ Guardrail: pregunta fuera de dominio.")
            elif rag_response.guardrail_triggered == "low_confidence":
                st.warning("🛡️ Guardrail: baja confianza en el material recuperado.")
            render_citations(rag_response.citations)

        msg = {
            "role": "assistant",
            "content": strip_sources_block(rag_response.answer),
            "citations": rag_response.citations,
            "llm_model": rag_response.llm_model,
            "guardrail": rag_response.guardrail_triggered,
            "tts_audio_bytes": tts_audio_for_msg,
        }
        st.session_state.messages.append(msg)
        save_message(student_id, "assistant", strip_sources_block(rag_response.answer))
    except Exception as pipeline_err:
        st.error(f"Pipeline error: {pipeline_err}")

    st.rerun()
