"""
06_servidor_interactivo.py
LIA - Tutor Virtual Gamificado por WhatsApp
Tesis de Grado - Colombo Americano
==============================================
Requisitos (pip install):
    flask twilio openai faiss-cpu numpy python-dotenv

Variables de entorno necesarias (.env o sistema):
    OPENAI_API_KEY
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_WHATSAPP  → ej: whatsapp:+14155238886

Ejecución:
    python 06_servidor_interactivo.py
    (En otra terminal) ngrok http 5000
    → Pegar la URL de ngrok en el Webhook de Twilio Sandbox.
"""

import os
import time
import threading

import faiss
import numpy as np
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ─────────────────────────────────────────────
app = Flask(__name__)

cliente_ai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
cliente_twilio = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Número de origen de la Sandbox (ej: whatsapp:+14155238886)
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP")

# Diccionario en memoria: clave = número E.164, valor = dict de sesión
sesiones: dict = {}

# Ruta al índice FAISS (carpeta src/faiss_index_lia junto a este archivo)
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
RUTA_FAISS = os.path.join(BASE_PATH, "src", "faiss_index_lia")

# Parámetros de inactividad
INACTIVIDAD_SEGUNDOS = 300   # 5 minutos
INTERVALO_MONITOR    = 30    # revisar cada 30 s

# ─────────────────────────────────────────────
# MONITOR DE INACTIVIDAD (hilo daemon)
# ─────────────────────────────────────────────
def revisar_inactividad() -> None:
    """
    Corre en segundo plano. Cada INTERVALO_MONITOR segundos revisa si
    algún usuario lleva más de INACTIVIDAD_SEGUNDOS sin escribir.
    Si es así, le envía un aviso por WhatsApp y borra su sesión.
    """
    while True:
        ahora = time.time()
        for numero in list(sesiones.keys()):
            ultimo = sesiones[numero].get("ultimo_acceso", ahora)
            if ahora - ultimo > INACTIVIDAD_SEGUNDOS:
                try:
                    cliente_twilio.messages.create(
                        from_=TWILIO_WHATSAPP_FROM,
                        body=(
                            "⏰ *LIA:* Cerramos la sesión por inactividad.\n\n"
                            "¡No te preocupes! Escribe *Hola* cuando quieras volver "
                            "y seguimos juntos. 😊"
                        ),
                        to=numero
                    )
                except Exception as err:
                    print(f"[INACTIVIDAD] Error al enviar aviso a {numero}: {err}")
                finally:
                    sesiones.pop(numero, None)
        time.sleep(INTERVALO_MONITOR)


_hilo_monitor = threading.Thread(target=revisar_inactividad, daemon=True)
_hilo_monitor.start()

# ─────────────────────────────────────────────
# BÚSQUEDA RAG (FAISS + text-embedding-3-small)
# ─────────────────────────────────────────────
def buscar_en_libro(query: str, nivel: str = "Unit 1") -> str:
    """
    Busca en el índice FAISS local el fragmento más relevante para `query`.
    Si el nivel es principiante fuerza el contexto hacia 'Unit 1 basics'.
    Devuelve el texto del fragmento o un fallback educativo.
    """
    try:
        index = faiss.read_index(os.path.join(RUTA_FAISS, "index.faiss"))

        with open(os.path.join(RUTA_FAISS, "texts.txt"), "r", encoding="utf-8") as f:
            textos = f.readlines()

        # Para principiantes ancla la búsqueda al vocabulario de Unit 1
        busqueda = f"Unit 1 basics {query}" if nivel == "Unit 1" else query

        resp = cliente_ai.embeddings.create(
            input=[busqueda],
            model="text-embedding-3-small"
        )
        vector = np.array([resp.data[0].embedding], dtype="float32")
        _, idx = index.search(vector, k=1)

        pos = int(idx[0][0])
        if 0 <= pos < len(textos):
            return textos[pos].strip()
        return "Focus on basic greetings: Hello, Hi, What's your name, Nice to meet you."

    except Exception as err:
        print(f"[FAISS] Error en búsqueda: {err}")
        return "Focus on basic greetings: Hello, Hi, What's your name, Nice to meet you."


# ─────────────────────────────────────────────
# HELPERS DE PREGUNTAS
# ─────────────────────────────────────────────
def _generar_primera_pregunta(sesion: dict) -> str:
    """Genera la Pregunta 1/5 usando RAG."""
    contexto = buscar_en_libro("basic greetings introductions", nivel="Unit 1")
    prompt = (
        f"Eres LIA, tutora de inglés empática y paciente para estudiantes colombianos.\n"
        f"Usando SOLO este contexto del libro:\n---\n{contexto}\n---\n"
        f"Genera UNA sola pregunta corta y clara en inglés para un estudiante principiante.\n"
        f"REGLAS ABSOLUTAS:\n"
        f"- Jamás incluyas la respuesta ni pistas directas dentro de la pregunta.\n"
        f"- La pregunta debe ser comprensible para alguien que apenas empieza.\n"
        f"- Solo escribe la pregunta, sin explicaciones adicionales."
    )
    resp = cliente_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.7
    )
    return resp.choices[0].message.content.strip()


def _generar_siguiente_pregunta(pregunta_anterior: str, numero_pregunta: int) -> str:
    """Genera la pregunta N/5, diferente a la anterior."""
    prompt = (
        f"Eres LIA, tutora de inglés empática para estudiantes colombianos principiantes.\n"
        f"La pregunta anterior fue: \"{pregunta_anterior}\"\n"
        f"Genera UNA sola pregunta DIFERENTE, corta y clara en inglés para nivel principiante.\n"
        f"REGLAS ABSOLUTAS:\n"
        f"- Jamás incluyas la respuesta ni pistas directas.\n"
        f"- No repitas la pregunta anterior.\n"
        f"- Solo escribe la nueva pregunta, sin nada más."
    )
    resp = cliente_ai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.9
    )
    return resp.choices[0].message.content.strip()


# ─────────────────────────────────────────────
# MOTOR PRINCIPAL DE LIA
# ─────────────────────────────────────────────
def motor_lia(numero: str, mensaje: str) -> str:
    """
    Recibe el número del alumno y el mensaje.
    Maneja el estado de sesión y devuelve UN SOLO string de respuesta.
    Los párrafos internos se separan con \\n\\n para mejor legibilidad en WhatsApp.
    """
    msg = mensaje.strip().lower()
    ahora = time.time()

    # ── Nuevo usuario o saludo reinicia sesión ──
    if numero not in sesiones or msg in ("hola", "hola!", "hello", "hi", "inicio"):
        sesiones[numero] = {
            "paso": "menu",
            "estrellas": 0,
            "pregunta_n": 1,
            "pregunta_actual": "",
            "ultimo_acceso": ahora
        }
        return (
            "¡Hola! 😊 Soy *LIA*, tu tutora de inglés del Colombo Americano.\n\n"
            "Estoy aquí para ayudarte a aprender de forma divertida. ¿Qué quieres hacer?\n\n"
            "1️⃣ Empezar carrera ⭐\n"
            "2️⃣ Ver mis estrellas 🌟\n"
            "3️⃣ Ayuda ❓\n\n"
            "_Responde con el número de tu opción._"
        )

    sesion = sesiones[numero]
    sesion["ultimo_acceso"] = ahora

    # ════════════════════════════════════════
    # ESTADO: MENÚ
    # ════════════════════════════════════════
    if sesion["paso"] == "menu":

        if msg == "1":
            sesion["paso"] = "jugando"
            sesion["pregunta_n"] = 1
            pregunta = _generar_primera_pregunta(sesion)
            sesion["pregunta_actual"] = pregunta
            return (
                "¡Genial, vamos allá! 🚀\n\n"
                f"*Pregunta 1/5:*\n{pregunta}\n\n"
                "_Escribe tu respuesta en inglés._"
            )

        elif msg == "2":
            estrellas = sesion.get("estrellas", 0)
            if estrellas == 0:
                return (
                    "Todavía no tienes estrellas ⭐, ¡pero eso está a punto de cambiar!\n\n"
                    "Escribe *1* para empezar tu carrera y ganar la primera. 💪"
                )
            return (
                f"✨ Llevas *{estrellas} estrella{'s' if estrellas != 1 else ''}* acumulada{'s' if estrellas != 1 else ''}.\n\n"
                "¡Sigue así! Escribe *1* para sumar más. 🌟"
            )

        elif msg == "3":
            return (
                "🤖 *¿Cómo funciona LIA?*\n\n"
                "• Escribe *1* para jugar y practicar inglés.\n"
                "• Te haré 5 preguntas. Cada respuesta correcta = 1 ⭐.\n"
                "• Si te equivocas, te explico y lo intentamos de nuevo.\n"
                "• Escribe *Hola* en cualquier momento para volver a este menú.\n\n"
                "_¡Tú puedes lograrlo! 💛_"
            )

        else:
            return (
                "Hmm, no reconocí esa opción. 😅\n\n"
                "Por favor responde con:\n"
                "1️⃣ Empezar carrera\n"
                "2️⃣ Ver estrellas\n"
                "3️⃣ Ayuda"
            )

    # ════════════════════════════════════════
    # ESTADO: JUGANDO (evaluación de respuesta)
    # ════════════════════════════════════════
    if sesion["paso"] == "jugando":
        n_pregunta = sesion["pregunta_n"]
        pregunta_actual = sesion["pregunta_actual"]

        prompt_eval = (
            "Eres LIA, una tutora de inglés colombiana: dulce, empática, paciente y motivadora.\n"
            "Tu alumno es estudiante principiante del Colombo Americano.\n\n"
            f"Pregunta que se le hizo: \"{pregunta_actual}\"\n"
            f"Respuesta del alumno: \"{mensaje}\"\n\n"
            "TAREA:\n"
            "1. Evalúa si la respuesta es correcta o incorrecta.\n"
            "2. Si es CORRECTA: comienza tu respuesta EXACTAMENTE con la palabra 'CORRECTO' "
            "(en mayúsculas), luego felicita al alumno calurosamente y da un mini tip "
            "en español de máximo 2 oraciones.\n"
            "3. Si es INCORRECTA: explica el error amablemente en ESPAÑOL simple, "
            "anima al alumno a intentarlo de nuevo. NUNCA reveles la respuesta correcta. "
            "NO empieces con la palabra CORRECTO.\n"
            "4. Responde de forma breve (máximo 4 oraciones). Usa emojis con moderación."
        )

        eval_resp = cliente_ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_eval}],
            max_tokens=200,
            temperature=0.6
        )
        feedback = eval_resp.choices[0].message.content.strip()
        es_correcto = feedback.upper().startswith("CORRECTO")

        # ── Respuesta CORRECTA ──
        if es_correcto:
            sesion["estrellas"] += 1
            sesion["pregunta_n"] += 1

            # ¿Terminó la carrera?
            if sesion["pregunta_n"] > 5:
                total = sesion["estrellas"]
                sesion["paso"] = "menu"
                emoji_trofeo = "🏆" if total == 5 else "🌟"
                return (
                    f"{feedback}\n\n"
                    f"{emoji_trofeo} *¡Carrera completada!*\n"
                    f"Conseguiste *{total}/5 estrellas*.\n\n"
                    f"{'¡Perfecto, eres una estrella! 🌠' if total == 5 else '¡Muy bien hecho! Cada vez mejoras más. 💪'}\n\n"
                    "Escribe *1* para jugar otra ronda o *Hola* para volver al menú."
                )

            # Siguiente pregunta
            nueva_pregunta = _generar_siguiente_pregunta(
                pregunta_actual, sesion["pregunta_n"]
            )
            sesion["pregunta_actual"] = nueva_pregunta
            return (
                f"{feedback}\n\n"
                f"⭐ Estrellas totales: *{sesion['estrellas']}*\n\n"
                f"*Pregunta {sesion['pregunta_n']}/5:*\n{nueva_pregunta}\n\n"
                "_Escribe tu respuesta en inglés._"
            )

        # ── Respuesta INCORRECTA (no avanza) ──
        return (
            f"{feedback}\n\n"
            f"💪 ¡Inténtalo de nuevo! Recuerda la pregunta:\n_{pregunta_actual}_"
        )

    # Fallback de seguridad
    sesion["paso"] = "menu"
    return "Algo salió mal por aquí. 😕 Escribe *Hola* para volver al menú."


# ─────────────────────────────────────────────
# ENDPOINT WEBHOOK DE TWILIO
# ─────────────────────────────────────────────
@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    """
    Recibe los webhooks de Twilio Sandbox.
    CRÍTICO: Se usa un ÚNICO tw_resp.message() para evitar que la
    Sandbox colapse con múltiples globos de texto.
    """
    try:
        numero  = request.values.get("From", "").strip()
        mensaje = request.values.get("Body", "").strip()

        print(f"[MENSAJE] De: {numero} | Texto: {mensaje!r}")

        if not numero or not mensaje:
            # Twilio a veces envía pings vacíos; responder vacío es válido.
            return str(MessagingResponse())

        respuesta = motor_lia(numero, mensaje)

        tw_resp = MessagingResponse()
        # ▶ UN SOLO mensaje concatenado — soluciona el colapso de la Sandbox
        tw_resp.message(respuesta)

        print(f"[RESPUESTA] A: {numero} | {respuesta[:80]}...")
        return str(tw_resp)

    except Exception as err:
        print(f"[ERROR FATAL] {err}")
        tw_resp = MessagingResponse()
        tw_resp.message(
            "Uy, tuve un pequeño mareo digital 😵‍💫\n\n"
            "Por favor escribe *Hola* para reiniciar nuestra conversación."
        )
        return str(tw_resp)


# ─────────────────────────────────────────────
# ARRANQUE
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  LIA - Tutor Virtual Gamificado")
    print("  Servidor Flask corriendo en :5000")
    print("=" * 50)
    # debug=False en producción para no reiniciar el hilo daemon
    app.run(host="0.0.0.0", port=5000, debug=False)