"""
Guardrails de LIA-Colombo AI.

- is_in_domain: clasificación de dominio (ESL vs fuera de tema).
- detect_low_confidence: umbral sobre scores de retrieval.
- heuristic_domain_check: filtro barato antes del LLM-as-judge.
"""
from __future__ import annotations
import re
from typing import Iterable

from src.config import (
    ENABLE_DOMAIN_GUARDRAIL,
    ENABLE_LOW_CONFIDENCE_GUARDRAIL,
    LOW_CONFIDENCE_THRESHOLD,
    OPENAI_API_KEY,
    LLM_UTILITY_MODEL,
)
from src.prompts import DOMAIN_CHECK_PROMPT

# ==========================================
# Heurística rápida (palabras clave)
# ==========================================
_ESL_KEYWORDS = {
    # Gramática
    "present", "past", "future", "perfect", "progressive", "continuous",
    "simple", "auxiliar", "auxiliary", "verb", "verbo", "tense", "tiempo",
    "do", "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "should", "must", "might", "may", "modal",
    # Vocabulario / temas del curso
    "vocabulario", "vocabulary", "palabra", "word", "significa", "mean",
    "traducir", "translate", "translation", "inglés", "ingles", "english",
    "pronunciación", "pronunciation", "pronouncing",
    # Conversación / curso
    "conversación", "conversation", "dialogue", "dialogo", "hablar", "speak",
    "escribir", "write", "leer", "read", "escuchar", "listen",
    "colombo", "fundamental", "unidad", "unit", "lección", "leccion", "lesson",
    "ejercicio", "exercise", "práctica", "practice",
}

_OFF_DOMAIN_HINTS = {
    # Programacion / tech
    "python", "javascript", "código", "codigo", "programming", "programar",
    "software", "tecnologia", "tecnología",
    # Cocina / comida
    "receta", "recipe", "cocina", "cocinar", "cocino", "cocinas",
    "preparar", "preparo", "ingrediente", "ingredientes",
    # Salud / medicina
    "medicina", "médico", "medico", "doctor", "enfermedad",
    "sintoma", "síntoma", "tratamiento",
    # Politica / finanzas
    "política", "politica", "elecciones", "presidente", "gobierno",
    "bitcoin", "crypto", "criptomoneda", "inversión", "inversion", "bolsa",
    # Deportes
    "fútbol", "futbol", "deporte", "deportes", "equipo", "jugador",
    # Geografia / viajes (no idiomas)
    "viaje", "turismo", "país", "pais",
    # Entretenimiento
    "película", "pelicula", "serie", "música", "musica", "celebridad",
}


def heuristic_domain_check(query: str) -> str:
    """Clasificacion barata por keywords. Devuelve IN_DOMAIN, OFF_DOMAIN o UNKNOWN.

    Usa word boundaries para evitar falsos positivos por subcadena.
    Ejemplo: "pasta" NO debe matchear "past".
    """
    q = query.lower()

    # Match de caracteres del alfabeto ingles embebidos en comillas -> muy probable ESL
    if re.search(r"['\"][a-zA-Z ]+['\"]", query):
        return "IN_DOMAIN"

    def _count_word_matches(text: str, keywords) -> int:
        n = 0
        for kw in keywords:
            # re.escape protege caracteres especiales; word boundaries evitan falsos positivos
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, text):
                n += 1
        return n

    off = _count_word_matches(q, _OFF_DOMAIN_HINTS)
    esl = _count_word_matches(q, _ESL_KEYWORDS)

    if off > 0 and esl == 0:
        return "OFF_DOMAIN"
    if esl >= 1:
        return "IN_DOMAIN"
    return "UNKNOWN"


ALWAYS_IN_DOMAIN = [
    "chat", "talk", "conversation", "practice", "hobby", "hobbies",
    "free time", "weekend", "family", "tell me", "let's", "lets",
    "speaking", "pronunciation", "what is", "what's", "what does", "what do",
    "how do", "how does", "how much", "how many", "how do you say", "how to say",
    "can you", "please", "help me",
    "i want", "i would", "i like", "i love", "i need",
    "numbers", "number", "colors", "color", "days", "day",
    "months", "month", "years", "year",
    "cuanto", "cuánto", "cuantos", "cuántos", "cuanta", "cuánta",
    "cuál", "cual", "cuáles",
    "matemáticas", "matematicas", "math",
    "número", "numero", "suma", "resta",
    "multiply", "divide", "plus", "minus", "times",
    "equals", "igual", "es igual", "más", "menos",
]


def is_in_domain(query: str, llm=None) -> bool:
    """
    Determina si la query pertenece al dominio ESL.
    Primero heurística; si es UNKNOWN, consulta LLM como juez.
    """
    if not ENABLE_DOMAIN_GUARDRAIL:
        return True

    # Siempre IN_DOMAIN si contiene palabras clave conversacionales
    query_lower = query.lower()
    if any(kw in query_lower for kw in ALWAYS_IN_DOMAIN):
        return True

    verdict = heuristic_domain_check(query)
    if verdict == "IN_DOMAIN":
        return True
    if verdict == "OFF_DOMAIN":
        # Preguntas de cultura general muy cortas → IN_DOMAIN (LIA las convierte en lección)
        if len(query.strip()) <= 25:
            return True
        return False

    # Ambiguo → LLM juez
    if llm is None:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(
                model=LLM_UTILITY_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0.0,
            )
        except Exception:
            # Si el LLM utilitario no está disponible, no bloqueamos
            return True

    try:
        prompt = DOMAIN_CHECK_PROMPT.format(query=query)
        resp = llm.invoke(prompt).content.strip().upper()
        return "OFF_DOMAIN" not in resp
    except Exception:
        return True  # fail-open


def detect_low_confidence(scores: Iterable[float]) -> bool:
    """
    True si el top score está bajo el umbral configurado (retrieval poco confiable).
    Acepta scores crudos de similarity (mayores = mejores).
    """
    if not ENABLE_LOW_CONFIDENCE_GUARDRAIL:
        return False
    scores_list = list(scores)
    if not scores_list:
        return True
    return max(scores_list) < LOW_CONFIDENCE_THRESHOLD
