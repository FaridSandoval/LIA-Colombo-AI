# 🤖 LIA — Tutor Virtual Gamificado por WhatsApp

This project is a part of the **Proyecto de Innovación Tecnológica** course in the Applied Artificial Intelligence Master, Universidad Icesi, Cali Colombia.

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
* **Backend:** Python 3.10+, LangChain, LangGraph
* **Frontend:** Streamlit (web application)
* **LLM:** Ollama (local models: qwen3.5:2B, mistral, tinyllama)
* **Embeddings:** Nomic Embed Text v2 (via Ollama)
* **Vector DB:** Chroma (persistent, local storage)
* **Document Processing:** PyPDF2, openpyxl, UnstructuredExcelLoader
* **Data Management:** Pandas, openpyxl
* **Text Splitting:** LangChain RecursiveCharacterTextSplitter

---

## Project Description

LIA is a **web-based intelligent tutoring platform** for the Colombo Americano language institute. It provides personalized, AI-powered tutoring through a Retrieval-Augmented Generation (RAG) architecture combined with an intelligent agent system (LangGraph). Students interact with a conversational chatbot via Streamlit that retrieves relevant pedagogical material and generates contextual responses.

**Key Features:**
- **Web-based Interface:** Streamlit application with role-based access (Admin, Student)
- **Local LLM Processing:** All inference runs locally via Ollama (no external API calls)
- **RAG System:** Documents indexed in Chroma, retrieving top-k similar passages for context injection
- **Intelligent Agent:** LangGraph agent with tool calling for semantic search and context retrieval
- **Multi-format Document Support:** Ingests PDF, TXT, Markdown, and XLSX files
- **Role-based UI:** Admin panel for document management; Student panel for tutoring sessions
- **Token Optimization:** Conversation history summarization to reduce context window usage

**Data sources:**
- Pedagogical documents in `data/raw/` (PDF, TXT, MD, XLSX formats)
- Student records in `data/user/estudiantes_dummies.xlsx` with fields: ID Number, Student Name, Course, Status, Final Score, Teacher Feedback
- Vector embeddings stored persistently in `data/chroma_db/`

**Gamification flow:**
1. **Student Login** → Enter ID Number to access personalized session
2. **Chat Interface** → Ask questions about the course material
3. **Intelligent Responses** → Agent retrieves relevant passages and generates contextual answers
4. **Context Awareness** → System considers student's course, feedback, and conversation history
5. **Admin Features** → Upload new documents, manage knowledge base (Admin role only)

---

## Getting Started

### Prerequisites
- Python 3.10+
- [Ollama](https://ollama.ai/) installed and running
- Virtual environment (venv or conda)

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/tu_usuario/LIA-Colombo-AI.git
   cd LIA-Colombo-AI
   ```

2. Create and activate virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

3. Install dependencies from `pyproject.toml`:
   ```powershell
   pip install -e .
   ```
   Or using `uv`:
   ```powershell
   uv pip sync pyproject.toml
   ```

4. Download Ollama models:
   ```powershell
   ollama pull qwen3.5:2B
   # OR for better quality (requires more RAM):
   ollama pull mistral
   ollama pull tinyllama
   ```

5. Start Ollama server (in a separate terminal):
   ```powershell
   ollama serve
   ```

6. Place your files in the correct locations:
   - Pedagogical documents → `data/raw/` (PDF, TXT, MD, XLSX)
   - Student records → `data/user/estudiantes_dummies.xlsx`

7. Run the Streamlit application:
   ```powershell
   streamlit run app.py
   ```
   Application opens at `http://localhost:8501`

### First Use
- **Login (Student):** Use any ID Number from `data/user/estudiantes_dummies.xlsx`
- **Login (Admin):** Use `Admin` as the ID Number to access admin panel
- **Admin Panel:** Upload documents via "Actualizar Base de Conocimiento" button

---

## Repository Structure

```
LIA-Colombo-AI/
├── app.py                          ← Main Streamlit application
├── pyproject.toml                  ← Project dependencies
├── data/
│   ├── raw/                        ← User-uploaded documents (PDF, TXT, MD, XLSX)
│   ├── user/
│   │   └── estudiantes_dummies.xlsx ← Student database for login
│   ├── chroma_db/                  ← Persistent vector store (auto-generated)
│   └── faiss_index/                ← Legacy FAISS indexes
├── src/
│   ├── __init__.py
│   ├── config.py                   ← Configuration (models, paths, hyperparameters)
│   ├── document_loader.py          ← Multi-format document ingestion
│   ├── embeddings.py               ← Chroma vector store setup
│   └── llm_chain.py                ← LangGraph agent with RAG tools
├── .gitignore
├── README.md
└── SETUP.md
```

**Key Modules:**
- `app.py` — Streamlit UI with login, chat interface, and admin panel
- `src/config.py` — Centralized configuration (LLM model, chunk size, paths)
- `src/document_loader.py` — Loads PDF, TXT, MD, XLSX files and splits them
- `src/embeddings.py` — Manages Chroma vector store and embedding model
- `src/llm_chain.py` — LangGraph agent with RAG retrieval tool and context summarization

---

## Featured Code / Components / Deliverables

### Core Application
* **[`app.py`](app.py)** — Main Streamlit application
  - Role-based login (Admin/Student)
  - Chat interface with streaming responses
  - Admin panel for document management
  - Session state management

### RAG & LLM Pipeline
* **[`src/llm_chain.py`](src/llm_chain.py)** — LangGraph intelligent agent
  - RAG tool for semantic search
  - Conversation history summarization
  - Dynamic prompt injection with context
  - Middleware-based context enrichment

* **[`src/embeddings.py`](src/embeddings.py)** — Vector store management
  - Chroma integration
  - Embedding model initialization (Ollama)
  - Document persistence and retrieval

* **[`src/document_loader.py`](src/document_loader.py)** — Multi-format document ingestion
  - Supports: PDF, TXT, Markdown, XLSX
  - Automatic chunking and splitting
  - Metadata preservation (source tracking)

### Configuration
* **[`src/config.py`](src/config.py)** — Centralized configuration
  - Model selection (qwen3.5:2B, mistral, tinyllama)
  - Chunk size and overlap tuning (CHUNK_SIZE=300, CHUNK_OVERLAP=50)
  - Path management for data directories
  - LLM temperature and system prompts

### Legacy Components (Phase 1 — WhatsApp/Flask Architecture)
* `src/06_servidor_interactivo.py` — Flask API server
* `src/05_motor_proactivo.py` — Proactive messaging engine
* `src/03_entrenar_memoria_rag.py` — FAISS index training
