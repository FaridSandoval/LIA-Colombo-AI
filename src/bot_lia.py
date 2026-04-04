import os
from dotenv import load_dotenv
from openai import OpenAI
from twilio.rest import Client

# ==========================================
# 1. CONFIGURACIÓN DE LAS LLAVES (TUS CREENCIALES)
# ==========================================
load_dotenv()

# 1. Configuración de las LLAVES (Invocando a la caja fuerte .env)
OPENAI_CLAVE = os.getenv("OPENAI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# El número de Twilio Sandbox (Lo ideal es guardarlo en el .env también)
NUMERO_TWILIO = os.getenv("TWILIO_NUMBER") 

# TU NÚMERO DE PRUEBA 
MI_CELULAR = os.getenv("MY_PHONE_NUMBER")

# ==========================================
# 2. INICIALIZAMOS LOS MOTORES
# ==========================================
cliente_ai = OpenAI(api_key=OPENAI_CLAVE)
cliente_whatsapp = Client(TWILIO_SID, TWILIO_TOKEN)

def generar_y_enviar_whatsapp(nombre, feedback):
    print(f"\n🧠 1. LIA está redactando el mensaje para {nombre}...")
    
    # --- EL CEREBRO (Generación del mensaje) ---
    instrucciones = f"""
    Eres LIA, asistente académica del Colombo Americano.
    Contacta al estudiante de forma proactiva y empática por WhatsApp.
    Estudiante: {nombre}
    Feedback: {feedback}
    Reglas: Saluda amigablemente, aborda el feedback (ofrece ayuda si es académico o empatía si faltó), usa máximo 3 oraciones cortas, incluye un emoji y despídete invitando a responder.
    """
    
    try:
        respuesta = cliente_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": instrucciones}],
            temperature=0.7
        )
        mensaje_lia = respuesta.choices[0].message.content
        print(f"✅ Mensaje redactado:\n{mensaje_lia}")
        
        # --- LA BOCA (Envío por Twilio) ---
        print(f"\n📤 2. Entregando el mensaje al cartero (Twilio)...")
        
        mensaje_enviado = cliente_whatsapp.messages.create(
            from_=NUMERO_TWILIO,
            body=mensaje_lia,
            to=MI_CELULAR
        )
        
        print(f"🚀 ¡ÉXITO! Mensaje enviado. ID de entrega: {mensaje_enviado.sid}")
        print("📱 ¡Revisa tu celular, Farid!")

    except Exception as e:
        print(f"❌ Error en el proceso: {e}")

# ==========================================
# 3. PRUEBA EN VIVO CON TUS DATOS DEL COLOMBO
# ==========================================
print("--- INICIANDO PROTOTIPO LIA ---")

# Vamos a simular que LIA detectó a Marylin en tu Excel y decidió escribirle
generar_y_enviar_whatsapp(
    nombre="Marylin",
    feedback="La estudiante no puede ser evaluada porque no se presentó a las primeras 5 clases."
)