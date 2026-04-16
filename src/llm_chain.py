from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain.agents.middleware import dynamic_prompt, ModelRequest
from langchain.chat_models import init_chat_model
from src.config import LLM_MODEL_NAME, OLLAMA_BASE_URL

# Instanciamos el modelo de chat
model = init_chat_model(LLM_MODEL_NAME)

def get_agent_executor(vector_store):
    
    # --- TOOL: Recuperación de contexto ---
    @tool(response_format="content_and_artifact")
    def retrieve_context(query: str):
        """Busca información relevante en los documentos locales para responder dudas."""
        retrieved_docs = vector_store.similarity_search(query, k=3)
        serialized = "\n\n".join(
            (f"Fuente: {doc.metadata.get('source', 'N/A')}\nContenido: {doc.page_content}")
            for doc in retrieved_docs
        )
        return serialized, retrieved_docs

    tools = [retrieve_context]

    # --- MIDDLEWARE: Inyección dinámica de contexto ---
    @dynamic_prompt
    def prompt_with_context(request: ModelRequest) -> str:
        # El mensaje del usuario ahora contiene el bloque [DATOS DEL ESTUDIANTE ACTUAL]
        # Extraemos el contenido para la búsqueda semántica
        last_query = request.state["messages"][-1].content
        
        # Buscamos en Chroma usando la consulta del usuario
        retrieved_docs = vector_store.similarity_search(last_query, k=2)
        docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

        return (
            "Eres un tutor de inglés experto del Centro Colombo Americano. "
            "Tu objetivo es ayudar al estudiante basándote en su perfil y el feedback del profesor. "
            "Si el feedback dice que debe practicar 'Past Progressive', orienta tus ejemplos hacia allá. "
            "Usa el contexto de los libros/documentos para dar respuestas precisas."
            f"\n\n[CONTEXTO DE DOCUMENTOS]:\n{docs_content}"
        )

    # Creamos el agente
    # Nota: El agente usará las herramientas para acciones explícitas 
    # y el middleware para contexto implícito.
    agent = create_agent(model, tools=tools, middleware=[prompt_with_context])
    return agent