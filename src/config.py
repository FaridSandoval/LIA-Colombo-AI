import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env (si existe en la raíz del proyecto)
load_dotenv()

# ==========================================
# 1. RUTAS DEL SISTEMA DE ARCHIVOS
# ==========================================
# Resuelve la ruta absoluta de la raíz del proyecto (dos niveles arriba de config.py)
BASE_DIR = Path(__file__).resolve().parent.parent

# Definición de directorios de datos
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"

# Crear directorios necesarios automáticamente en la primera ejecución
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. CONFIGURACIÓN DE EMBEDDINGS Y CHUNKING
# ==========================================
# Modelo de embeddings local en Ollama.
EMBEDDING_MODEL_NAME = "nomic-embed-text-v2-moe:latest" # O embeddinggemma:latest

# Parámetros para la división de documentos (Text Splitting)
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 500))  # Reducido de 1000
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 50))  # Reducido de 150

# ==========================================
# 3. CONFIGURACIÓN DE INFERENCIA (OLLAMA & LLM)
# ==========================================
# Conexión local a Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Modelo LLM local en Ollama
LLM_MODEL_NAME = "ollama:qwen3.5:2B"


# Temperatura baja (0.1 - 0.3) es ideal para RAG, ya que reduce las alucinaciones 
# y obliga al modelo a ceñirse al contexto recuperado.
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", 0.2)) 

CHROMA_DB_DIR = DATA_DIR / "chroma_db"
CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

# ==========================================
# 4. CONFIGURACIÓN DEL SISTEMA / PROMPT
# ==========================================
# Prompt base enfocado en un comportamiento didáctico y estructurado
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Eres un asistente pedagógico experto. Utiliza únicamente el contexto proporcionado "
    "para responder a las preguntas de forma clara, didáctica y enfocada en facilitar "
    "el aprendizaje del usuario. Si la respuesta no se encuentra en el contexto, "
    "indícalo de manera directa sin inventar información."
)