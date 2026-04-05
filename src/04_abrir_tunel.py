import os
import time
from pyngrok import ngrok, conf

# =================================================================
# MÓDULO DE CONECTIVIDAD: TÚNEL NGROK
# =================================================================

# Configuración del token de autenticación
# Este token es obligatorio para que el túnel sea estable y no se cierre.
NGROK_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
conf.get_default().auth_token = NGROK_TOKEN

def iniciar_puente_comunicacion():
    """
    Función de enlace externo:
    Crea una URL pública temporal que redirige el tráfico de Twilio
    hacia el servidor local de LIA (Puerto 5000). 
    Es el componente que permite la bidireccionalidad del chat.
    """
    print("--- INICIANDO PUENTE DE CONECTIVIDAD LIA ---")
    
    try:
        # Abrimos el túnel en el puerto 5000 (donde correrá Flask)
        url_publica = ngrok.connect(5000)
        
        print("\n" + "="*50)
        print("¡TÚNEL ACTIVADO EXITOSAMENTE!")
        print(f"URL PÚBLICA PARA TWILIO: {url_publica.public_url}")
        print("="*50)
        
        print("\nINSTRUCCIÓN PARA TU TESIS:")
        print("1. Copia la URL de arriba (la que empieza por https).")
        print("2. Pégala en el campo 'Webhook' de tu Sandbox de Twilio.")
        print("3. No cierres esta ventana mientras estés probando el chat.")
        
        # Mantenemos el proceso vivo
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"\nError al intentar abrir el túnel: {e}")
        print("Verifica que no tengas otra instancia de ngrok abierta.")

if __name__ == "__main__":
    iniciar_puente_comunicacion()