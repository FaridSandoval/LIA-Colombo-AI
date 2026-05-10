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


@st.cache_resource
def _warmup_ollama():
    """Carga el modelo en VRAM al iniciar la app, antes del primer usuario."""
    import requests as _req
    from src.config import OLLAMA_BASE_URL, LLM_MODEL_NAME
    try:
        _req.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": LLM_MODEL_NAME, "prompt": " ", "keep_alive": "30m"},
            timeout=10,
        )
    except Exception:
        pass
    return True

_warmup_ollama()

st.markdown("""
<style>
/* Sidebar institucional */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1A2744 0%, #0D1B3E 100%);
}
[data-testid="stSidebar"] * { color: white !important; }
[data-testid="stSidebar"] .stButton > button {
    background-color: #E8C23A;
    color: #1A2744;
    border: none;
    border-radius: 12px;
    font-weight: 700;
    font-size: 15px;
    padding: 10px 16px;
    width: 100%;
    margin-bottom: 6px;
    box-shadow: 0 3px 8px rgba(232,194,58,0.35);
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #EB8E35;
    color: white;
    box-shadow: 0 5px 14px rgba(235,142,53,0.4);
}

/* Fuente más grande en chat */
[data-testid="stChatMessage"] {
    font-size: 17px !important;
    line-height: 1.65 !important;
}

/* Header */
h1 { border-bottom: 4px solid #E8C23A; padding-bottom: 8px; }

/* Botones principales más llamativos */
.stButton > button {
    background: linear-gradient(135deg, #E8C23A 0%, #EB8E35 100%);
    color: #1A2744;
    border: none;
    border-radius: 14px;
    font-weight: 800;
    font-size: 16px;
    padding: 10px 18px;
    box-shadow: 0 4px 12px rgba(232,194,58,0.4);
    transition: all 0.2s ease;
    letter-spacing: 0.3px;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #EB8E35 0%, #E8C23A 100%);
    color: white;
    box-shadow: 0 8px 20px rgba(235,142,53,0.5);
    transform: translateY(-2px);
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    border: 2px solid #E8C23A !important;
    border-radius: 12px !important;
    font-size: 16px !important;
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


def strip_nota_block(text: str) -> str:
    """Elimina el bloque 'Nota: este tema no está cubierto...' del LLM."""
    import re
    cleaned = re.sub(r'\n*Nota:.*?próxima clase\.?', '', text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def filtered_stream(raw_stream):
    """Filtra bloque 'Nota:' del stream sin producir artefactos."""
    GUARD = 10  # buffer de seguridad para detectar patrones partidos
    output = ""
    yielded = 0
    for chunk in raw_stream:
        output += chunk
        nota_idx = output.find("\nNota")
        if nota_idx != -1:
            safe = output[:nota_idx].rstrip()
            if len(safe) > yielded:
                yield safe[yielded:]
            return
        # Yield solo hasta GUARD chars antes del final (por si "\nNota" está partido)
        safe_end = max(yielded, len(output) - GUARD)
        if safe_end > yielded:
            yield output[yielded:safe_end]
            yielded = safe_end
    # Stream terminó sin Nota — yield lo que queda
    if len(output) > yielded:
        yield output[yielded:]


def correction_then_stream(correction_text: str, stream_gen):
    """Yield corrección primero, luego el stream del LLM."""
    if correction_text:
        yield correction_text
    yield from stream_gen


def get_grammar_correction(user_text: str) -> str:
    """Detecta errores y devuelve corrección formateada, o cadena vacía si está correcto."""
    from openai import OpenAI
    import os
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "user",
            "content": (
                "You are a strict grammar checker. "
                "Check ONLY for spelling mistakes and clear grammatical errors "
                "(wrong verb conjugation, missing subject, wrong tense). "
                "Do NOT change vocabulary, word choice, or style. "
                "Do NOT 'improve' sentences that are already correct. "
                "If the sentence is grammatically correct, return exactly: OK\n"
                "If there are errors, return ONLY the corrected sentence, nothing else.\n\n"
                f"Text: {user_text}"
            )
        }],
        max_tokens=100,
        temperature=0,
    )
    corrected = resp.choices[0].message.content.strip()
    import re
    def _normalize(t): return re.sub(r'[^\w\s]', '', t).lower().strip()
    if corrected == "OK" or _normalize(corrected) == _normalize(user_text):
        return ""
    return f'✏️ *Correction:* "{corrected}" ✓\n\n'


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

st.title(f"🤖 LIA — Hello, {primer_nombre_pila}!")

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

        if st.button("📖  My Book", key="opt1", use_container_width=True):
            st.session_state.pending_prompt = "I have a question about my book"
            st.session_state.last_prompt_was_audio = False
            st.rerun()
        if st.button("💬  Conversation", key="opt2", use_container_width=True):
            st.session_state.pending_prompt = "I want to practice conversation in English"
            st.session_state.last_prompt_was_audio = False
            st.rerun()
        if st.button("📝  Grammar", key="opt3", use_container_width=True):
            st.session_state.pending_prompt = "Can you explain a grammar topic?"
            st.session_state.last_prompt_was_audio = False
            st.rerun()
        if st.button("✏️  My Writing", key="opt4", use_container_width=True):
            st.session_state.pending_prompt = "Can you check my writing?"
            st.session_state.last_prompt_was_audio = False
            st.rerun()
        if st.button("🔍  Something Else", key="opt5", use_container_width=True):
            pass

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
            _query = prompt
            if detect_translation_request(prompt):
                _query = (
                    "⚠️ INSTRUCCIÓN OBLIGATORIA: El estudiante no entendió tu respuesta anterior. "
                    "Debes responder TODO en español simple y claro. "
                    "Explica lo que dijiste antes en español. "
                    "Al final agrega exactamente: 'Now you try! 💪'\n\n"
                    f"Mensaje del estudiante: {prompt}"
                )

            with st.spinner("Consultando tus materiales de clase..."):
                stream_gen, citations, guardrail = pipeline.query_stream(
                    user_query=_query,
                    user_info=user_info,
                    conversation_history=st.session_state.messages[:-1],
                )

            correction_prefix = ""
            try:
                correction_prefix = get_grammar_correction(prompt)
            except Exception:
                pass
            full_answer = st.write_stream(
                correction_then_stream(correction_prefix, filtered_stream(stream_gen))
            )
            full_answer = strip_nota_block(full_answer)

            from src.llm_chain import RAGResponse
            rag_response = RAGResponse(
                answer=full_answer,
                citations=citations,
                guardrail_triggered=guardrail,
                llm_model=st.session_state.selected_llm,
            )
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
