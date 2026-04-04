import os
import pandas as pd
from datetime import datetime
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

# Configuración
MI_LLAVE_REAL = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = MI_LLAVE_REAL
cliente = OpenAI(api_key=MI_LLAVE_REAL)

app = Flask(__name__)
sesiones_estudiantes = {}

# RUTAS DE ARCHIVOS
RUTA_ESTUDIANTES = os.path.join("data", "estudiantes.xlsx")
RUTA_PACING = os.path.join("data", "pacing.xlsx")

# ==========================================
# LÓGICA DE RECONOCIMIENTO Y CALENDARIO
# ==========================================

def obtener_datos_estudiante(celular):
    try:
        df = pd.read_excel(RUTA_ESTUDIANTES)
        estudiante = df[df['Celular'] == celular]
        if not estudiante.empty:
            datos = estudiante.iloc[0]
            # Calcular qué clase le toca hoy
            fecha_inicio = pd.to_datetime(datos['Fecha_Inicio'])
            hoy = datetime.now()
            # Cálculo simple: días transcurridos (puedes ajustar según días hábiles)
            dias_pasados = (hoy - fecha_inicio).days
            clase_estimada = (dias_pasados // 1) + 1 # Ajustar lógica según intensidad horaria
            
            return {
                "nombre": datos['Nombre'],
                "curso": datos['Curso'],
                "clase": clase_estimada
            }
    except Exception as e:
        print(f"Error base de datos: {e}")
    return None

def obtener_tema_pacing(curso, clase):
    try:
        df = pd.read_excel(RUTA_PACING)
        filtro = df[(df['Curso'] == curso) & (df['Clase'] == clase)]
        if not filtro.empty:
            return filtro.iloc[0]['Tema']
    except:
        return "General Review"
    return "English Skills"

# ==========================================
# INTERACCIÓN CON LIA
# ==========================================

def interactuar_con_lia(celular, mensaje_usuario):
    # 1. Identificar al alumno
    info = obtener_datos_estudiante(celular)
    if not info:
        return "Sorry! I don't recognize this number. Please contact the Colombo front desk to register. 🏫"

    estado = sesiones_estudiantes.get(celular, {"checkpoint": 0, "historial": []})
    tema_hoy = obtener_tema_pacing(info['curso'], info['clase'])
    
    # --- BIENVENIDA PERSONALIZADA ---
    if estado["checkpoint"] == 0:
        instrucciones = f"""You are LIA. Welcome {info['nombre']} back! 
        He/She is in {info['curso']}, Lesson {info['clase']}. 
        Today's topic is {tema_hoy}. 
        Start the 10-question race now with Question 1. Use emojis! 🚀"""
        estado["checkpoint"] = 1
    
    # --- CARRERA ---
    elif estado["checkpoint"] < 10:
        instrucciones = f"""Student: {info['nombre']}. Checkpoint: {estado['checkpoint']}/10. 
        Topic: {tema_hoy}. 
        If correct, say 'Checkpoint {estado['checkpoint']}/10 complete! ✅' and ask next. 
        If wrong, explain in Spanish then ask in English."""
    
    # --- META ---
    else:
        instrucciones = f"Congratulate {info['nombre']} for finishing his/her 10 daily goals! 🏆"

    # Llamada a OpenAI
    res = cliente.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": instrucciones}] + estado["historial"][-4:] + [{"role": "user", "content": mensaje_usuario}]
    )
    
    respuesta_ia = res.choices[0].message.content
    
    # Actualizar estado
    estado["historial"].append({"role": "user", "content": mensaje_usuario})
    estado["historial"].append({"role": "assistant", "content": respuesta_ia})
    if "checkpoint" in respuesta_ia.lower() or "correct" in respuesta_ia.lower():
        estado["checkpoint"] += 1
    
    sesiones_estudiantes[celular] = estado
    return respuesta_ia

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    celular = request.values.get('From', '')
    mensaje = request.values.get('Body', '')
    respuesta = interactuar_con_lia(celular, mensaje)
    
    tw_resp = MessagingResponse()
    tw_resp.message(respuesta)
    return str(tw_resp)

if __name__ == "__main__":
    app.run(port=5000)