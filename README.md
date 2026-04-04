# LIA: Learning Intelligence Assistant
### Proyecto de Tesis: Inteligencia Artificial cómo tutor educativo
**Autores:** Farid Sandoval, Ivan Marín, Josué Cobaleda

---

## Descripción
**LIA** es un asistente virtual proactivo diseñado para el Centro Cultural Colombo Americano. Su objetivo principal es reducir la deserción en el programa *Fundamental 1* mediante tutorías personalizadas vía WhatsApp.

El sistema utiliza una arquitectura **RAG (Retrieval-Augmented Generation)**, lo que significa que no responde "lo que cree", sino que consulta el currículo oficial (**CLT**) y el libro *Speak Your Mind* para dar respuestas alineadas con la metodología institucional.

## Funcionalidades Principales
* **Detección de Riesgo:** Escanea los registros académicos para identificar estudiantes con estado "Fail".
* **Contacto Proactivo:** Envía mensajes automáticos a las 8:00 PM ofreciendo ayuda.
* **Tutoría RAG:** Responde dudas gramaticales usando el contexto real del libro de texto.
* **Personalización:** Conoce el nombre del estudiante y el tema exacto que vio en su última clase.

## Requisitos Técnicos
* **Lenguaje:** Python 3.10 o superior.
* **IA:** API de OpenAI (Modelo GPT-4o-mini).
* **Base de Datos de Vectores:** FAISS (para la memoria del libro).
* **Comunicación:** Twilio API (WhatsApp Sandbox).
* **Servidor local:** Flask + Ngrok.

---

## Instrucciones

### 1. Preparación del Entorno
Clona el repositorio y descarga las librerías necesarias:
```bash
pip install -r requirements.txt
```

### 2. Configuración de Seguridad (Archivo .env)
Por seguridad (Habeas Data y protección de presupuesto), nunca subas tus llaves de API al repo. Debes crear un archivo llamado `.env` en la raíz del proyecto y pegar lo siguiente con tus credenciales:

```
OPENAI_API_KEY=tu_clave_aqui
TWILIO_ACCOUNT_SID=tu_sid_aqui
TWILIO_AUTH_TOKEN=tu_token_aqui
NGROK_AUTH_TOKEN=tu_token_ngrok_aqui
MY_PHONE_NUMBER=whatsapp:+57XXXXXXXXXX
```

### 3. Estructura de Datos
Para que el código funcione, los archivos de seguimiento deben estar en la carpeta `data/`:

* **data/estudiantes.xlsx:** Listas de clase y estados.
* **data/pacing.xlsx:** Cronograma de temas (Pacing).

## Justificación de Tesis
Este proyecto demuestra cómo la IA Generativa puede optimizar los costos operativos de una institución educativa. Al automatizar el primer contacto de tutoría, el Support Teacher puede enfocarse en casos de alta complejidad, mientras LIA resuelve dudas inmediatas basadas en el método Communicative Language Teaching (CLT).

## Aviso de Privacidad
Este proyecto cumple con la Ley 1581 de 2012 (Colombia). Los datos utilizados en este repositorio son ficticios o han sido anonimizados para proteger la identidad de los estudiantes reales del Colombo Americano.