from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from src.config import OLLAMA_BASE_URL, LLM_MODEL_NAME, LLM_TEMPERATURE, DEFAULT_SYSTEM_PROMPT


class RAGChain:
    def __init__(self, llm, retriever, prompt):
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt

    def invoke(self, inputs):
        query = inputs.get("input")
        if query is None:
            raise ValueError("Input dictionary must contain the key 'input'.")

        docs = self.retriever.get_relevant_documents(query)
        context = "\n\n".join(
            f"Source: {doc.metadata.get('source', 'Desconocido')}\n{doc.page_content}"
            for doc in docs
        )

        formatted = self.prompt.format_prompt(context=context, input=query)
        messages = formatted.to_messages()
        response = self.llm.invoke(messages)

        return {
            "answer": response.content,
            "context": docs,
        }


def get_rag_chain(vectorstore):
    llm = ChatOllama(
        model=LLM_MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=LLM_TEMPERATURE,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", DEFAULT_SYSTEM_PROMPT),
        ("human", "Contexto:\n{context}\n\nPregunta: {input}"),
    ])

    retriever = vectorstore.as_retriever()
    return RAGChain(llm, retriever, prompt)
