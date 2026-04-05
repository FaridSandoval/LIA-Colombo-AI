# 🤖 Proyecto LIA — Guía de Configuración

Este repositorio contiene el código fuente de **LIA**, una asistente virtual basada en Inteligencia Artificial (Arquitectura RAG) diseñada para interactuar con los estudiantes por WhatsApp, ofrecer retroalimentación proactiva y realizar sesiones de tutoría gamificadas.

---

## 📋 Requisitos Previos

Antes de ejecutar cualquier script, asegúrate de tener lo siguiente:

- **Python:** Versión instalada en tu sistema. El proyecto fue adaptado para ser compatible incluso con versiones recientes como Python 3.14.
- **Poppler:** Necesario para el Paso 02 (Procesamiento OCR). La carpeta `bin` de Poppler debe estar ubicada dentro de la carpeta `src/`.
- **Cuentas de terceros:**
  - Cuenta de OpenAI (API Key)
  - Cuenta de Twilio (Account SID, Auth Token y Sandbox de WhatsApp configurado)
  - Cuenta de ngrok (Auth Token)

---

## 🛠️ Configuración del Entorno

### 1. Instalar dependencias

Abre una terminal en la raíz del proyecto y ejecuta:

```powershell
py -m pip install openai faiss-cpu numpy pandas openpyxl flask twilio pyngrok
```

> **Nota:** Se evita usar LangChain y Pydantic para prevenir problemas de compatibilidad con versiones nuevas de Python.

### 2. Configurar Variables de Entorno

Cada vez que abras una nueva terminal para correr el proyecto, debes cargar las llaves de acceso. En PowerShell, ejecuta:

```powershell
$env:OPENAI_API_KEY     = "sk-TU_LLAVE_OPENAI"
$env:TWILIO_ACCOUNT_SID = "TU_TWILIO_SID"
$env:TWILIO_AUTH_TOKEN  = "TU_TWILIO_TOKEN"
$env:TWILIO_WHATSAPP    = "whatsapp:+14155238886"
$env:NGROK_AUTH_TOKEN   = "TU_TOKEN_NGROK"
```

> ⚠️ Nunca subas estas claves al repositorio. El archivo `.env` está incluido en `.gitignore`.

---

## 🚀 Guía de Ejecución Paso a Paso

Los scripts están enumerados en el orden exacto en el que deben ejecutarse. Todos los comandos asumen que estás dentro de la carpeta `src/`.

### Paso 02 — Digitalización del Libro (OCR)

Convierte el PDF del libro pedagógico en texto plano para que la IA pueda leerlo.

```powershell
py 02_extraer_texto_ocr.py
```

✅ Resultado esperado: creación del archivo `libro_texto.txt`.

---

### Paso 03 — Entrenamiento del Cerebro (RAG)

Toma el archivo de texto y lo convierte en una base de datos vectorial (Embeddings) para búsquedas ultrarrápidas.

```powershell
py 03_entrenar_memoria_rag.py
```

✅ Resultado esperado: creación de la carpeta `faiss_index_lia/`.

---

### Paso 04 — Abrir el Túnel (ngrok)

Crea una URL pública temporal para que Twilio pueda comunicarse con tu computadora local.

```powershell
py 04_abrir_tunel.py
```

El script mostrará una URL como `https://xxxx.ngrok-free.dev`. Luego:

1. Copia esa URL
2. Ve a la consola de Twilio → **Sandbox Settings**
3. Pégala en el campo *"When a message comes in"* agregando `/whatsapp` al final
4. Guarda los cambios

> ⚠️ **IMPORTANTE:** Deja esta terminal **ABIERTA**. Si la cierras, el chat dejará de funcionar.

---

### Paso 05 — Motor Proactivo *(Opcional)*

Escanea el archivo `personal_data.xlsx`, detecta estudiantes con estado `Fail` y les envía un mensaje automatizado con un consejo basado en el libro.

Abre una nueva terminal, carga las variables de entorno y ejecuta:

```powershell
py 05_motor_proactivo.py
```

---

### Paso 06 — Servidor Interactivo (El Chatbot)

Enciende el servidor Flask que maneja la conversación en tiempo real, la gamificación (estrellas) y las consultas al libro.

En una terminal separada (con las variables cargadas), ejecuta:

```powershell
py 06_servidor_interactivo.py
```

💬 **Prueba:** Escribe `Hola` al número de Twilio en tu WhatsApp para ver el menú y comenzar la carrera.
