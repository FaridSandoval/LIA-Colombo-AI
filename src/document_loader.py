import pandas as pd
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import RAW_DATA_DIR, CHUNK_SIZE, CHUNK_OVERLAP

def process_excel_by_rows(file_path):
    """Tratamiento especial para Excel: 1 Fila = 1 Chunk"""
    df = pd.read_excel(file_path)
    excel_docs = []
    
    for index, row in df.iterrows():
        # Unimos todas las columnas en un string descriptivo: "Columna1: Valor, Columna2: Valor..."
        content = " | ".join([f"{col}: {val}" for col, val in row.items()])
        
        # Creamos el objeto Document con metadatos de la fila
        doc = Document(
            page_content=content,
            metadata={"source": str(file_path), "row": index, "type": "structured"}
        )
        excel_docs.append(doc)
    
    return excel_docs

def load_and_split_documents():
    docs_to_split = []
    final_documents = []

    # 1. Cargar formatos de texto (PDF, TXT, MD)
    text_extensions = {
        "*.pdf": PyPDFLoader,
        "*.txt": TextLoader,
        "*.md": TextLoader
    }

    for glob_pattern, loader_cls in text_extensions.items():
        loader = DirectoryLoader(str(RAW_DATA_DIR), glob=glob_pattern, loader_cls=loader_cls)
        docs_to_split.extend(loader.load())

    # Aplicar división por palabras a los documentos de texto
    if docs_to_split:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        final_documents.extend(text_splitter.split_documents(docs_to_split))

    # 2. Cargar y procesar archivos Excel de forma diferenciada
    excel_files = list(RAW_DATA_DIR.glob("./*.xlsx"))
    for file in excel_files:
        final_documents.extend(process_excel_by_rows(file))

    return final_documents