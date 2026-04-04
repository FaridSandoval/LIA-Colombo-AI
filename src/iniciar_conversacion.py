import os
from twilio.rest import Client

# Credenciales de Twilio (Para el tutor: Autenticacion del cliente REST para envio proactivo)
# Debes reemplazar estos valores con los que aparecen en tu consola de Twilio
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
cliente = Client(account_sid, auth_token)

# Envio del mensaje inicial (Para el tutor: Disparador de la conversacion)
mensaje = cliente.messages.create(
    from_='whatsapp:+14155238886', # Este es el numero estandar del Sandbox de Twilio
    body='Hola! Soy LIA tu asistente virtual del Colombo Americano Cali. Hoy tuviste tu clase numero 5 en tu curso Fundamental, quieres practicar con ejercicios hoy?',
    to='whatsapp:+573154569754' # Asegurate de que este sea tu numero exacto
)

print(f"Mensaje de bienvenida enviado con exito. ID: {mensaje.sid}")