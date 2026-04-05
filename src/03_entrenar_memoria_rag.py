import os
import numpy as np
import faiss
from openai import OpenAI

# =================================================================
# CEREBRO DE LIA: VERSIÓN DE ALTA COMPATIBILIDAD (SIN LANGCHAIN)
# =================================================================

base_path = os.path.dirname(os.path.abspath(__file__))
archivo_texto = os.path.join(base_path, "libro_texto.txt")
carpeta_memoria = os.path.join(base_path, "faiss_index_lia")

# Cargamos la llave desde el sistema
OPENAI_CLAVE = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_CLAVE)

def crear_memoria():
    print("--- INICIANDO CONSTRUCCIÓN DE MEMORIA (MODO DIRECTO) ---")

    if not os.path.exists(archivo_texto):
        print(f"Error: No se encuentra {archivo_texto}")
        return

    try:
        # 1. Leer el libro
        with open(archivo_texto, "r", encoding="utf-8") as f:
            texto = f.read()

        # 2. Fragmentar el texto (Chunks de 1000 caracteres)
        print("Fragmentando contenido...")
        chunks = [texto[i:i+1000] for i in range(0, len(texto), 900)]

        # 3. Crear Embeddings usando OpenAI directamente
        print(f"Generando vectores para {len(chunks)} fragmentos...")
        
        # Obtenemos los vectores numéricos
        response = client.embeddings.create(
            input=chunks,
            model="text-embedding-3-small"
        )
        embeddings = np.array([data.embedding for data in response.data]).astype('float32')

        # 4. Guardar en FAISS
        print("Guardando base de datos vectorial...")
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)

        # Guardamos el índice y los textos para usarlos después
        if not os.path.exists(carpeta_memoria):
            os.makedirs(carpeta_memoria)
            
        faiss.write_index(index, os.path.join(carpeta_memoria, "index.faiss"))
        with open(os.path.join(carpeta_memoria, "texts.txt"), "w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(chunk.replace("\n", " ") + "\n")

        print("\n" + "="*50)
        print("¡MEMORIA CREADA CON ÉXITO!")
        print("="*50)

    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    crear_memoria()