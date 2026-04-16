from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from src.config import EMBEDDING_MODEL_NAME, CHROMA_DB_DIR

def get_embedding_model():
    return OllamaEmbeddings(model=EMBEDDING_MODEL_NAME)

def create_or_load_vectorstore(documents=None):
    embeddings = get_embedding_model()
    vector_store = Chroma(
        collection_name="local_rag_agent",
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DB_DIR)
    )
    if documents:
        vector_store.add_documents(documents)
    return vector_store