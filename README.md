# 🤖 LIA — Tutor Virtual Gamificado por WhatsApp

This project is a part of the **Proyecto 1 de Innovación Tecnológica** course in the Applied Artificial Intelligence Master, Universidad Icesi, Cali Colombia.

#### -- Project Status: Active

---

## Contributing Members

**Instructor: Luis Ferro Diez (https://github.com/Ohtar10)**

#### Members:

| Name | Email |
|------|-------|
| Farid Sandoval (https://github.com/FaridSandoval) | farid.sandoval@icesi.edu.co |
| Ivan Moran (https://github.com/IM-333) | ivan.moran@icesi.edu.co |
| Josué Cobaleda (https://github.com/josue-cobaleda) | josue.cobaleda@icesi.edu.co |

## Contact
* Feel free to contact the team leader or the instructor with any questions or if you are interested in contributing!

---

## Project Intro / Objective

The purpose of this project is to develop **LIA** (*Learning Interactive Assistant*), a gamified virtual tutor that interacts with students of the Colombo Americano language institute via WhatsApp. LIA leverages a Retrieval-Augmented Generation (RAG) architecture built on the institution's official pedagogical book to deliver contextually accurate responses. The system conducts gamified tutoring sessions of 5 questions per round, awards stars for correct answers, and proactively reaches out to students identified as at-risk based on academic records. The goal is to provide accessible, personalized, and engaging English-language support outside the classroom.

### Partner
* **Colombo Americano** — Binational Center, Cali, Colombia
* [www.colomboamericano.edu.co](https://www.colomboamericano.edu.co)

### Methods Used
* Retrieval-Augmented Generation (RAG)
* Text Embeddings & Semantic Search
* Conversational AI / Prompt Engineering
* Gamification (stars, levels, progress tracking)
* Proactive Messaging (automated outreach)
* Session State Management (in-memory, inactivity detection)

### Technologies
* Python 3.14
* OpenAI API (`gpt-4o-mini`, `text-embedding-3-small`)
* FAISS (`faiss-cpu`) + NumPy — vector index without LangChain
* Flask — webhook server
* Twilio — WhatsApp Sandbox messaging
* ngrok — local HTTPS tunnel
* Pandas + openpyxl — student data processing
* Poppler — PDF OCR preprocessing

---

## Project Description

LIA addresses a common gap in language learning: students lack accessible, on-demand support between classes. The system ingests the Colombo Americano's official English textbook via OCR, chunks it into passages, and indexes those passages as vector embeddings in a local FAISS database. When a student asks a question or starts a tutoring session, LIA retrieves the most semantically relevant passage and uses it as grounding context for `gpt-4o-mini` — ensuring responses are faithful to the institution's curriculum.

**Data sources:**
- Colombo Americano pedagogical PDF (processed via OCR in `02_extraer_texto_ocr.py`)
- Student academic records (`personal_data.xlsx`) with fields: name, phone, unit, status (Pass/Fail)

**Key challenges solved:**
- **Twilio Sandbox silence bug:** The sandbox collapses silently when TwiML contains multiple `<Message>` elements. Fixed by concatenating all response text into a single `tw_resp.message()` call separated by `\n\n`.
- **Python 3.14 compatibility:** LangChain and Pydantic are incompatible with Python 3.14. All RAG logic was reimplemented directly with `faiss-cpu` and `numpy`.
- **Session state:** Managed in-memory with a `sesiones` dictionary keyed by phone number, including inactivity detection via a background daemon thread (5-minute timeout, 30-second polling interval).

**Gamification flow:**
1. Student greets LIA → receives main menu
2. Selects option 1 → 5-question career begins (RAG-grounded questions)
3. Each correct answer = +1 star; incorrect answers receive empathetic feedback in Spanish without revealing the answer
4. After 5 questions, total stars are shown and session returns to menu

---

## Getting Started

1. Clone this repo:
   ```bash
   git clone https://github.com/tu_usuario/proyecto-lia.git
   cd proyecto-lia
   ```

2. Install dependencies:
   ```powershell
   py -m pip install openai faiss-cpu numpy pandas openpyxl flask twilio pyngrok
   ```
   > **Note:** LangChain and Pydantic are intentionally excluded for Python 3.14 compatibility.

3. Place your files in the correct locations:
   - PDF textbook → `libro_pedagogico.pdf` (project root)
   - Student records → `personal_data.xlsx` (project root)
   - Poppler binaries → `src/bin/`

4. Set environment variables (run in every new terminal session):
   ```powershell
   $env:OPENAI_API_KEY     = "sk-..."
   $env:TWILIO_ACCOUNT_SID = "AC..."
   $env:TWILIO_AUTH_TOKEN  = "..."
   $env:TWILIO_WHATSAPP    = "whatsapp:+14155238886"
   $env:NGROK_AUTH_TOKEN   = "..."
   ```

5. Run the pipeline in order from the `src/` folder:

   | Step | Script | Output |
   |------|--------|--------|
   | 02 | `py 02_extraer_texto_ocr.py` | `libro_texto.txt` |
   | 03 | `py 03_entrenar_memoria_rag.py` | `faiss_index_lia/` |
   | 04 | `py 04_abrir_tunel.py` | ngrok HTTPS URL |
   | 05 *(optional)* | `py 05_motor_proactivo.py` | WhatsApp proactive messages |
   | 06 | `py 06_servidor_interactivo.py` | Live Flask server |

   > ⚠️ After step 04, paste the ngrok URL + `/whatsapp` into **Twilio Console → Sandbox Settings → "When a message comes in"** and keep that terminal open.

6. Test: send `Hola` to the Twilio Sandbox number on WhatsApp.

---

## Repository Structure

```
proyecto-lia/
├── src/
│   ├── bin/                      ← Poppler binaries (not tracked by git)
│   ├── faiss_index_lia/          ← Generated in step 03 (not tracked by git)
│   │   ├── index.faiss
│   │   └── texts.txt
│   ├── 02_extraer_texto_ocr.py
│   ├── 03_entrenar_memoria_rag.py
│   ├── 04_abrir_tunel.py
│   ├── 05_motor_proactivo.py
│   └── 06_servidor_interactivo.py
├── libro_pedagogico.pdf
├── personal_data.xlsx
├── .gitignore
└── README.md
```

---

## Featured Notebooks / Analysis / Deliverables

* [`06_servidor_interactivo.py`](src/06_servidor_interactivo.py) — Core chatbot server: Flask webhook, RAG pipeline, gamification engine, inactivity monitor
* [`05_motor_proactivo.py`](src/05_motor_proactivo.py) — Proactive outreach engine for at-risk students
* [`03_entrenar_memoria_rag.py`](src/03_entrenar_memoria_rag.py) — FAISS index construction from pedagogical text
* [Thesis Document](link) *(add link when available)*
* [Demo Video](link) *(add link when available)*
