import pandas as pd
import os
from openai import OpenAI
from twilio.rest import Client
# Importamos lo necesario para leer el libro (FAISS)
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

# ==========================================
# 1. TUS LLAVES MAESTRAS (Mantenemos tus datos)
# ==========================================
OPENAI_CLAVE = os.getenv("OPENAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
NUMERO_TWILIO = os.getenv("TWILIO WHATSAPP")
MI_CELULAR = os.getenv("MY_PHONE_NUMBER")

# Forzamos la llave para LangChain
os.environ["OPENAI_API_KEY"] = OPENAI_CLAVE

# 2. INICIALIZAMOS MOTORES
cliente_ai = OpenAI(api_key=OPENAI_CLAVE)
cliente_whatsapp = Client(TWILIO_SID, TWILIO_TOKEN)

# ==========================================
# 3. FUNCIÓN RAG: BUSCAR EN EL LIBRO
# ==========================================
def buscar_en_libro(tema):
    try:
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_CLAVE)
        # Buscamos la carpeta faiss_index_lia que creamos con cerebro_lia.py
        ruta_faiss = "src/faiss_index_lia" if os.path.exists("src/faiss_index_lia") else "faiss_index_lia"
        
        base_datos = FAISS.load_local(ruta_faiss, embeddings, allow_dangerous_deserialization=True)
        resultados = base_datos.similarity_search(tema, k=2)
        return "\n".join([doc.page_content for doc in resultados])
    except Exception as e:
        return f"Usa el método CLT del Colombo."

# ==========================================
# 4. LA BOCA DE LIA: GENERAR Y ENVIAR
# ==========================================
def enviar_whatsapp_lia(nombre, feedback):
    print(f"🧠 LIA consultando el libro para {nombre}...")
    
    # BUSQUEDA RAG
    contexto_libro = buscar_en_libro(feedback)
    
    instrucciones = f"""
    Eres LIA, asistente del Colombo Americano. 
    Tu misión es dar un consejo basado exclusivamente en el material oficial.
    
    FEEDBACK DEL PROFE: {feedback}
    CONTENIDO EXTRAÍDO DEL LIBRO: {contexto_libro}
    
    Reglas: 
    1. Saluda amigable. 
    2. Menciona una frase o vocabulario EXACTO que aparezca en el 'CONTENIDO DEL LIBRO'.
    3. Si el libro menciona una lección o unidad específica en el texto extraído, dila.
    4. Máximo 3 oraciones y usa emojis.
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
            to=MI_CELULAR
        )
        print(f"✅ Mensaje RAG enviado a tu WhatsApp para el caso de {nombre}.")
        
    except Exception as e:
        print(f"❌ Error con {nombre}: {e}")

# ==========================================
# 5. EJECUCIÓN AUTOMÁTICA
# ==========================================
if __name__ == "__main__":
    print("--- 🤖 INICIANDO LIA AUTOMATIZADA CON RAG ---")
    ruta_excel = os.path.join(os.path.dirname(os.path.abspath(__file__)), "personal_data.xlsx")

    try:
        df = pd.read_excel(ruta_excel, skiprows=7, header=None, engine='openpyxl')
        contador = 0
        for index, fila in df.iterrows():
            nombre, feedback, estado = fila[5], fila[45], fila[74]
            
            if pd.notna(nombre) and str(estado).strip() == "Fail":
                enviar_whatsapp_lia(nombre, feedback)
                contador += 1
                if contador == 2: break # Probamos con 2 para no gastar saldo de Twilio
        
        print(f"\n🏆 LIA procesó {contador} estudiantes con éxito.")
    except Exception as e:
        print(f"Error: {e}")