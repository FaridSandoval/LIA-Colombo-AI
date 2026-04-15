from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import RAW_DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP

def load_and_split_documents():
    # Soporta múltiples formatos en la carpeta data/raw
    loaders = {
        ".pdf": DirectoryLoader(str(RAW_DATA_DIR), glob="./*.pdf", loader_cls=PyPDFLoader),
        ".txt": DirectoryLoader(str(RAW_DATA_DIR), glob="./*.txt", loader_cls=TextLoader),
    }
    
    docs = []
    for loader in loaders.values():
        docs.extend(loader.load())

    # Estrategia de split recursivo para mantener coherencia semántica
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    return text_splitter.split_documents(docs)