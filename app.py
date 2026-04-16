import streamlit as st
import pandas as pd
from pathlib import Path
from src.document_loader import load_and_split_documents
from src.embeddings import create_or_load_vectorstore
from src.llm_chain import get_agent_executor  # Asegúrate de usar la versión agéntica sugerida
from src.config import RAW_DATA_DIR

# Configuración de página
st.set_page_config(page_title="LIA-Colombo AI Tutor", layout="wide", page_icon="🎓")

# --- CACHE PARA VECTORSTORE ---
@st.cache_resource
def get_vectorstore():
    """Carga el vectorstore una sola vez con caching."""
    return create_or_load_vectorstore()

# --- FUNCIONES DE APOYO ---
def get_user_data(id_number):
    """Busca al estudiante en el archivo Excel dummy."""
    file_path = Path("./data/user/estudiantes_dummies.xlsx")
    if not file_path.exists():
        return None
    
    df = pd.read_excel(file_path)
    # Aseguramos que el ID Number sea tratado como string para la comparación
    user_row = df[df['ID Number'].astype(str) == str(id_number)]
    
    if not user_row.empty:
        return user_row.iloc[0].to_dict()
    return None

# --- INICIALIZACIÓN DE ESTADOS ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = get_vectorstore()

# --- VISTA DE LOGIN ---
logged_in = st.session_state.get("logged_in", False)
user_info = st.session_state.get("user_info")

# Force login si no hay usuario
if not logged_in or user_info is None:
    st.container()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 LIA-Colombo AI Login")
        st.subheader("Plataforma de Tutoría Inteligente")
        with st.form("login_form"):
            id_input = st.text_input("Ingrese su ID Number (Documento de Identidad)")
            submit = st.form_submit_button("Ingresar")
            
            if submit:
                user_data = get_user_data(id_input)
                if user_data:
                    st.session_state.user_info = user_data
                    st.session_state.logged_in = True
                    st.success(f"Bienvenido(a), {user_data['Student Name']}")
                    st.rerun()
                else:
                    st.error("ID no encontrado. Verifique los datos.")
    st.stop()

# --- VISTA PRINCIPAL (POST-LOGIN) ---
# Recuperar user_info después del stop
user_info = st.session_state.get("user_info")
if not user_info:
    st.error("Error: No hay sesión activa. Por favor, inicie sesión de nuevo.")
    st.stop()

st.title(f"🤖 Tutor IA - Hola, {user_info['Student Name']}")

# Sidebar con info del estudiante y gestión de docs
with st.sidebar:
    # Verificar si es Admin
    is_admin = user_info.get('Student Name', '').lower() == 'admin'
    
    if is_admin:
        st.header("👤 Perfil del Admin")
        st.info(f"""
        **Rol:** Administrador  
        **Acceso:** Control Total
        """)
        
        st.divider()
        st.header("⚙️ Gestión de Documentos")
        if st.button("🔄 Actualizar Base de Conocimiento"):
            with st.spinner("Indexando..."):
                docs = load_and_split_documents()
                st.session_state.vectorstore = create_or_load_vectorstore(docs)
                st.success("Conocimiento actualizado.")
        
        with st.expander("📊 Estadísticas"):
            st.caption("Panel de control para administradores")
    else:
        st.header("👤 Perfil del Estudiante")
        st.info(f"""
        **Curso:** {user_info['Course']}  
        **Estado:** {user_info['Status']}  
        **Nota Actual:** {user_info['Final Score']}
        """)
        
        with st.expander("📝 Feedback del Profesor"):
            st.caption(user_info['Teacher Feedback'])
    
    st.divider()
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.session_state.user_info = None
        st.session_state.messages = []
        st.rerun()

# --- LÓGICA DEL CHAT AGÉNTICO ---

# Mostrar historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input de usuario
if prompt := st.chat_input("Escribe tu duda sobre la clase..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.vectorstore:
        # Obtenemos el agente (el middleware usará el vectorstore)
        # IMPORTANTE: Pasamos el contexto del usuario al agente
        agent = get_agent_executor(st.session_state.vectorstore)
        
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            
            # Construimos el prompt enriquecido con datos del usuario
            # Esto asegura que el agente sepa con quién habla antes de procesar
            user_context = f"""
            [DATOS DEL ESTUDIANTE ACTUAL]
            Nombre: {user_info['Student Name']}
            Curso: {user_info['Course']}
            Feedback previo: {user_info['Teacher Feedback']}
            Duda del usuario: {prompt}
            """
            
            with st.spinner("Consultando tutoría..."):
                for step in agent.stream(
                    {"messages": [{"role": "user", "content": user_context}]},
                    stream_mode="values"
                ):
                    last_message = step["messages"][-1]
                    full_response = last_message.content
                    placeholder.markdown(full_response)
            
            st.session_state.messages.append({"role": "assistant", "content": full_response})
    else:
        st.warning("El sistema no tiene base de conocimiento cargada.")