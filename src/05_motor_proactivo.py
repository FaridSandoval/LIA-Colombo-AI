import pandas as pd
import os
import numpy as np
import faiss
from openai import OpenAI
from twilio.rest import Client

# ==========================================
# 1. TUS LLAVES MAESTRAS
# ==========================================
OPENAI_CLAVE = os.getenv("OPENAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
NUMERO_TWILIO = "whatsapp:+14155238886" # Número estándar Sandbox
MI_CELULAR = os.getenv("MY_PHONE_NUMBER")

# 2. INICIALIZAMOS MOTORES
cliente_ai = OpenAI(api_key=OPENAI_CLAVE)
cliente_whatsapp = Client(TWILIO_SID, TWILIO_TOKEN)

base_path = os.path.dirname(os.path.abspath(__file__))
ruta_faiss = os.path.join(base_path, "faiss_index_lia")

# ==========================================
# 3. FUNCIÓN RAG: BUSCAR EN EL LIBRO (MODO COMPATIBLE)
# ==========================================
def buscar_en_libro(tema):
    try:
        # Cargamos el índice y los textos que guardamos en el Paso 03
        index = faiss.read_index(os.path.join(ruta_faiss, "index.faiss"))
        with open(os.path.join(ruta_faiss, "texts.txt"), "r", encoding="utf-8") as f:
            textos = f.readlines()

        # Convertimos el tema del profe en un vector
        resp = cliente_ai.embeddings.create(input=[tema], model="text-embedding-3-small")
        vector_busqueda = np.array([resp.data[0].embedding]).astype('float32')

        # Buscamos los 2 fragmentos más parecidos
        _, indices = index.search(vector_busqueda, k=2)
        
        contexto = ""
        for i in indices[0]:
            if i < len(textos):
                contexto += textos[i] + "\n"
        
        return contexto
    except Exception as e:
        print(f"Nota: No se pudo acceder a la memoria FAISS ({e}). Usando conocimiento general.")
        return "Focus on communicative language teaching (CLT) methods."

# ==========================================
# 4. LA BOCA DE LIA: GENERAR Y ENVIAR
# ==========================================
def enviar_whatsapp_lia(nombre, feedback):
    print(f"🧠 LIA consultando el libro para {nombre}...")
    
    contexto_libro = buscar_en_libro(feedback)
    
    instrucciones = f"""
    Eres LIA, asistente del Colombo Americano. 
    Tu misión es dar un consejo basado en el material oficial del libro.
    
    FEEDBACK DEL PROFE: {feedback}
    CONTENIDO DEL LIBRO: {contexto_libro}
    
    Reglas: 
    1. Saluda amigable. 
    2. Menciona vocabulario o frases que aparezcan en el 'CONTENIDO DEL LIBRO'.
    3. Máximo 3 oraciones y usa emojis.
    """
    
    try:
        respuesta = cliente_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": instrucciones}]
        )
        mensaje_final = respuesta.choices[0].message.content
        
        # ENVÍO REAL A WHATSAPP
        cliente_whatsapp.messages.create(
            from_=NUMERO_TWILIO,
            body=mensaje_final,
            to=MI_CELULAR # Enviamos a tu número para la prueba de tesis
        )
        print(f"✅ Mensaje RAG enviado a tu WhatsApp para el caso de {nombre}.")
        
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")

# ==========================================
# 5. EJECUCIÓN AUTOMÁTICA
# ==========================================
if __name__ == "__main__":
    print("--- 🤖 INICIANDO LIA AUTOMATIZADA CON RAG ---")
    ruta_excel = os.path.join(base_path, "personal_data.xlsx")

    try:
        df = pd.read_excel(ruta_excel, skiprows=7, header=None, engine='openpyxl')
        contador = 0
        for index, fila in df.iterrows():
            # Columnas según tu Excel: 5=Nombre, 45=Feedback, 74=Estado
            nombre, feedback, estado = fila[5], fila[45], fila[74]
            
            if pd.notna(nombre) and str(estado).strip() == "Fail":
                enviar_whatsapp_lia(nombre, feedback)
                contador += 1
                if contador == 2: break # Prueba controlada
        
        print(f"\n🏆 LIA procesó {contador} estudiantes con éxito.")
    except Exception as e:
        print(f"Error general: {e}")