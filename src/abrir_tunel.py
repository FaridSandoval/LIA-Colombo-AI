import os

from pyngrok import ngrok, conf
import time

# Configuracion del token de autenticacion (Para el tutor: Requisito de seguridad de ngrok)
conf.get_default().auth_token = os.getenv("NGROK_AUTH_TOKEN")

# Inicia el tunel apuntando al puerto 5000 (Para el tutor: Puente para recibir webhooks de Twilio)
url_publica = ngrok.connect(5000)
print(f"URL PUBLICA: {url_publica}")

# Bucle infinito para evitar que el script termine y cierre el tunel
print("Tunel activo. Presiona CTRL+C para cerrar.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Tunel cerrado manualmente.")