import os
from dotenv import load_dotenv
from docling.document_converter import DocumentConverter
from langchain_text_splitters import CharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

load_dotenv()

def entrenar_lia_con_libro():
    # 1. Ruta al libro que ya tienes en tu carpeta 'books'
    ruta_libro = "../books/studentbook.pdf" 
    
    print("📖 Docling está analizando el libro... Espera un momento.")
    converter = DocumentConverter()
    resultado = converter.convert(ruta_libro)
    texto = resultado.document.export_to_markdown()

    # 2. Partimos el libro en trozos para que quepan en la memoria de la IA
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    trozos = text_splitter.split_text(texto)

    # 3. Creamos la base de datos FAISS (El archivador)
    print("🧠 Creando índice de memoria (FAISS)...")
    embeddings = OpenAIEmbeddings()
    vector_db = FAISS.from_texts(trozos, embeddings)
    
    # 4. Guardamos esa memoria en una carpeta para no repetir esto siempre
    vector_db.save_local("faiss_index_lia")
    print("✅ ¡Listo! LIA ya se aprendió el libro y guardó la memoria en 'src/faiss_index_lia'.")

if __name__ == "__main__":
    entrenar_lia_con_libro()