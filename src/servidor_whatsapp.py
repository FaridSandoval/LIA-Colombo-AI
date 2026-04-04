import os
import pandas as pd
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

# Configuración de IA
OPENAI_CLAVE = os.getenv("OPENAI_API_KEY")
os.environ["OPENAI_API_KEY"] = OPENAI_CLAVE
cliente_ai = OpenAI(api_key=OPENAI_CLAVE)

app = Flask(__name__)
sesiones_estudiantes = {}

# --- CONFIGURACIÓN DE RUTAS Y DATOS ---
RUTA_PACING = os.path.join("data", "pacing.xlsx")
CURSO_ACTUAL = "Fundamental 1"  # Esto vendría de tu base de datos de alumnos
CLASE_NUMERO = 5               # La clase que el alumno tomó hoy
FALLA_DOCENTE = "the use of 'did' in questions" # Retroalimentación del profe

def obtener_tema_del_pacing():
    try:
        # Cargamos el Excel de la ruta que me diste
        df = pd.read_excel(RUTA_PACING)
        # Filtramos por curso y clase (Asegúrate que las columnas se llamen 'Curso' y 'Clase')
        filtro = df[(df['Curso'] == CURSO_ACTUAL) & (df['Clase'] == CLASE_NUMERO)]
        if not filtro.empty:
            return filtro.iloc[0]['Tema']
    except Exception as e:
        print(f"Error leyendo el Excel: {e}")
    return "General Grammar"

def leer_libro():
    if os.path.exists("src/libro_texto.txt"):
        with open("src/libro_texto.txt", "r", encoding="utf-8") as f:
            return f.read()[:2500]
    return "English Grammar Context."

def interactuar_con_llm(numero, mensaje_usuario, contexto_libro, tema_pacing):
    estado = sesiones_estudiantes.get(numero, {"checkpoint": 0, "historial": []})
    
    # Lógica de Bienvenida y Checkpoint Inicial
    if estado["checkpoint"] == 0:
        instruccion = f"""You are LIA, a friendly tutor from Colombo Americano Cali 🇨🇴.
        Today's class topic was: {tema_pacing}.
        The teacher noticed the student struggles with: {FALLA_DOCENTE}.
        Start a 10-checkpoint race. FOCUS on the teacher's note using the book context: {contexto_libro}.
        Rules: 
        1. Welcome the student warmly.
        2. Ask Question 1 about {tema_pacing} focusing on {FALLA_DOCENTE}.
        3. Use English and many emojis. 🏃‍♂️💨"""
        estado["checkpoint"] = 1
    
    # Lógica de cierre (Meta cumplida)
    elif estado["checkpoint"] >= 10:
        instruccion = f"""The student finished the 10 exercises! 🏆
        1. Give a SUPER SHORT and MOTIVATING message in English.
        2. Ask if they want more exercises or if they prefer to see you tomorrow.
        3. Be very kind. ✨"""
    
    # Lógica de la carrera (Checkpoints 1 al 9)
    else:
        instruccion = f"""You are LIA. Student is at checkpoint {estado['checkpoint']}/10.
        Current Topic: {tema_pacing}. Focus area: {FALLA_DOCENTE}.
        Evaluate the answer. If correct, celebrate and ask next question. 
        If incorrect, explain briefly and ask a new one.
        Use book content for examples: {contexto_libro}."""

    mensajes = [{"role": "system", "content": instruccion}]
    mensajes.extend(estado["historial"][-4:])
    mensajes.append({"role": "user", "content": mensaje_usuario})

    resp = cliente_ai.chat.completions.create(model="gpt-4o-mini", messages=mensajes, temperature=0.7)
    texto_ia = resp.choices[0].message.content
    
    # Guardar memoria
    estado["historial"].append({"role": "user", "content": mensaje_usuario})
    estado["historial"].append({"role": "assistant", "content": texto_ia})
    
    # Subir nivel si la IA valida positivamente
    if any(word in texto_ia.lower() for word in ["correct", "checkpoint", "done", "perfect"]):
        estado["checkpoint"] += 1

    sesiones_estudiantes[numero] = estado
    return texto_ia

@app.route("/whatsapp", methods=['POST'])
def whatsapp_reply():
    numero = request.values.get('From', '')
    mensaje = request.values.get('Body', '')
    
    tema_hoy = obtener_tema_del_pacing()
    contexto = leer_libro()
    
    respuesta_ia = interactuar_con_llm(numero, mensaje, contexto, tema_hoy)
    
    tw_resp = MessagingResponse()
    tw_resp.message(respuesta_ia)
    return str(tw_resp)

if __name__ == "__main__":
    app.run(port=5000)