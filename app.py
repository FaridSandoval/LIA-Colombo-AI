import streamlit as st
from src.document_loader import load_and_split_documents
from src.embeddings import create_or_load_vectorstore
from src.llm_chain import get_rag_chain
from src.config import EMBEDDING_MODEL_NAME

st.set_page_config(page_title="RAG Local Assistant", layout="wide")

st.title("🤖 Chatbot RAG Local (Ollama)")

# Sidebar para gestión de documentos
with st.sidebar:
    st.header("Gestión de Conocimiento")
    if st.button("🔄 Procesar / Actualizar Documentos"):
        with st.spinner("Indexando..."):
            try:
                docs = load_and_split_documents()
                st.session_state.vectorstore = create_or_load_vectorstore(docs)
                st.success("Índice actualizado con éxito.")
            except Exception as e:
                st.error(
                    "No se pudo indexar los documentos. "
                    "Asegúrate de que Ollama esté en ejecución y de que tu modelo "
                    "de embeddings local esté disponible.\n" + str(e)
                )

# Inicializar estado de la sesión
if "vectorstore" not in st.session_state:
    st.session_state.vectorstore = create_or_load_vectorstore()

if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar historial de chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input del usuario
if prompt := st.chat_input("¿En qué puedo ayudarte hoy?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if st.session_state.vectorstore:
        chain = get_rag_chain(st.session_state.vectorstore)
        
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                response = chain.invoke({"input": prompt})
                full_response = response["answer"]
                st.markdown(full_response)
                
                # Opcional: Mostrar fuentes
                with st.expander("Ver fuentes"):
                    for doc in response["context"]:
                        st.write(f"- {doc.metadata.get('source', 'Desconocido')}")
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
    else:
        st.warning("Por favor, procesa los documentos en la barra lateral antes de chatear.")