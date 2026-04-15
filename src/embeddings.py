from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from src.config import EMBEDDING_MODEL_NAME, FAISS_INDEX_DIR, OLLAMA_BASE_URL

def get_embedding_model():
    try:
        return OllamaEmbeddings(
            model=EMBEDDING_MODEL_NAME,
            base_url=OLLAMA_BASE_URL,
            validate_model_on_init=True,
        )
    except Exception as exc:
        raise RuntimeError(
            "No se pudo inicializar el modelo de embeddings local. "
            "Asegúrate de que Ollama esté en ejecución y de que el modelo "
            f"'{EMBEDDING_MODEL_NAME}' esté disponible en tu servidor local."
        ) from exc

def create_or_load_vectorstore(documents=None):
    embeddings = get_embedding_model()
    
    # Intentar cargar índice existente para ahorrar cómputo
    if (FAISS_INDEX_DIR / "index.faiss").exists():
        return FAISS.load_local(
            str(FAISS_INDEX_DIR), 
            embeddings, 
            allow_dangerous_deserialization=True
        )
    
    if documents:
        vectorstore = FAISS.from_documents(documents, embeddings)
        vectorstore.save_local(str(FAISS_INDEX_DIR))
        return vectorstore
    
    return None