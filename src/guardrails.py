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
    OLLAMA_BASE_URL,
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
    "python", "javascript", "código", "programming", "programar",
    "receta", "recipe", "cocina", "medicina", "médico", "doctor",
    "política", "politica", "elecciones", "bitcoin", "crypto",
}


def heuristic_domain_check(query: str) -> str:
    """Clasificación barata por keywords. Devuelve IN_DOMAIN, OFF_DOMAIN o UNKNOWN."""
    q = query.lower()

    # Match de caracteres del alfabeto inglés embebidos en comillas → muy probable ESL
    if re.search(r"['\"][a-zA-Z ]+['\"]", query):
        return "IN_DOMAIN"

    off = sum(1 for kw in _OFF_DOMAIN_HINTS if kw in q)
    esl = sum(1 for kw in _ESL_KEYWORDS if kw in q)

    if off > 0 and esl == 0:
        return "OFF_DOMAIN"
    if esl >= 1:
        return "IN_DOMAIN"
    return "UNKNOWN"


def is_in_domain(query: str, llm=None) -> bool:
    """
    Determina si la query pertenece al dominio ESL.
    Primero heurística; si es UNKNOWN, consulta LLM como juez.
    """
    if not ENABLE_DOMAIN_GUARDRAIL:
        return True

    verdict = heuristic_domain_check(query)
    if verdict == "IN_DOMAIN":
        return True
    if verdict == "OFF_DOMAIN":
        return False

    # Ambiguo → LLM juez
    if llm is None:
        try:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(
                model=LLM_UTILITY_MODEL,
                base_url=OLLAMA_BASE_URL,
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
