# 🤖 LIA — Tutor Virtual

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

The purpose of this project is to develop **LIA** (*Learning Intelligence Assistant*), a virtual conversational tutor that interacts with students of the Colombo Americano language institute (Fundamental Plus cycle, A2-B1 level). LIA leverages an advanced Retrieval-Augmented Generation (RAG) architecture built on the institution's official pedagogical materials to deliver contextually accurate and curriculum-aware responses. The goal is to extend the window of linguistic practice outside the classroom, offering an asynchronous pedagogical accompaniment that strictly respects the Communicative Language Teaching (CLT) methodology.

### Partner
* **Colombo Americano** — Binational Center, Cali, Colombia
* [www.colomboamericano.edu.co](https://www.colomboamericano.edu.co)

### Methods Used
* Curriculum-Aware Retrieval-Augmented Generation (RAG)
* Hybrid Retrieval (Semantic Search via Embeddings + Lexical BM25 + Reciprocal Rank Fusion)
* Contextual Retrieval & Guardrails
* Prompt Engineering & Role-playing
* RAGAS Framework for Technical Evaluation

### Technologies
* **Backend:** Python 3.11+, LangChain
* **Frontend:** Streamlit (web application)
* **LLM (Main Generation):** Ollama (local model: `gemma2:9b`)
* **LLM (Utility/Guardrails):** Ollama (local model: `qwen2.5:3b`)
* **Embeddings & Reranker:** BGE-M3, BGE-reranker-v2-m3
* **Vector DB:** Chroma (persistent local storage)
* **Evaluation:** RAGAS (using `gpt-4o-mini` as LLM judge)

---

## Project Description

LIA is a **web-based intelligent tutoring platform**. It provides personalized, AI-powered tutoring through a robust RAG architecture. Students interact with a conversational chatbot via Streamlit that retrieves relevant pedagogical material (grammar rules, vocabulary, audio transcripts) and generates contextual responses.

**Key Features:**
- **Curriculum Grounding:** Responses are strictly anchored to the Fundamental Plus syllabus, avoiding out-of-domain hallucinations.
- **Guardrails System:** Active filtering to reject off-domain questions and redirect the student to English learning topics.
- **Local LLM Processing:** Inference runs locally via Ollama ensuring data privacy and offline capability.
- **Hybrid Retrieval:** Combines BM25 and Vector Search with a Reranker for highly accurate context fetching.
- **High-Quality Corpus:** Curated ingestion of clean pedagogical materials (e.g., Murphy's Grammar, structured vocabulary lists).

**Data sources:**
- Pedagogical documents in `data/raw/` organized by source type (`grammar_reference`, `student_book`, `vocabulary`, `supplementary`).
- Vector embeddings stored persistently in `data/chroma_db/` (currently ~6,350 chunks).
- Evaluation datasets in `eval/golden_set.yaml`.

---

## Getting Started

### Prerequisites
- Windows 11 / PowerShell
- Python 3.11+
- `uv` package manager
- [Ollama](https://ollama.ai/) installed and running

### Installation

1. Clone this repository:
   ```bash
   git clone [https://github.com/tu_usuario/LIA-Colombo-AI.git](https://github.com/tu_usuario/LIA-Colombo-AI.git)
   cd LIA-Colombo-AI
   ```

2. Create and activate virtual environment using uv:
   ```powershell
   uv venv
   .venv\Scripts\activate
   $env:UV_LINK_MODE = "copy"
   ```

3. Install dependencies
   ```powershell
   uv sync
   ```

4. Download Ollama models:
   ```powershell
   ollama pull gemma2:9b
   ollama pull qwen2.5:3b
   ```

5. Set up your .env file (ensure OPENAI_API_KEY is set for RAGAS evaluation):
   OPENAI_API_KEY=your_key_here
   ENABLE_CONTEXTUAL_RETRIEVAL=true
   CONTEXTUAL_MAX_WORDS=60
   OLLAMA_BASE_URL=http://localhost:11434

6. Run the Streamlit application:
   ```powershell
   uv run streamlit run app.py
   ```
   Application opens at `http://localhost:8501`

---

## Repository Structure

```
LIA-Colombo-AI/
├── app.py                  ← Main Streamlit application
├── pyproject.toml / uv.lock← Project dependencies managed by uv
├── data/
│   ├── raw/                ← Source documents (PDF, MD, XLSX) categorized by source_type
│   ├── chroma_db/          ← Persistent vector store
│   └── quarantine/         ← Problematic files excluded from index (e.g., raw Teacher's Edition)
├── src/                    ← Core logic (RAG pipeline, document loaders, guardrails, prompts)
├── eval/                   ← RAGAS evaluation scripts, metrics, and golden_set.yaml
├── docs/
│   └── findings/           ← Technical documentation and audit findings
├── scripts/                ← Utility scripts for data cleaning and manual ingestion
├── .env                    ← Environment variables
└── README.md
```
