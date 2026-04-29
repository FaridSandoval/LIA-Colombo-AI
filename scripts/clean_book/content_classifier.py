"""
Clasificación de bloques:
- student_content: contenido principal del libro (la página visible al estudiante).
- teacher_note: tips, respuestas, notas didácticas (el plus del Teacher's Edition).
- noise: boilerplate, números de página, ruido a descartar.

Esta clasificación es lo que permite que el RAG pueda filtrar y devolver
respuestas distintas según el rol (estudiante vs docente).
"""
from __future__ import annotations

import logging
import re
from enum import Enum

from .pdf_extractor import Block

logger = logging.getLogger(__name__)


class ContentType(str, Enum):
    STUDENT_CONTENT = "student_content"
    TEACHER_NOTE = "teacher_note"
    NOISE = "noise"
    SECTION_HEADER = "section_header"   # Vocabulary, Grammar, etc.


def _matches_any_pattern(text: str, patterns: list[re.Pattern]) -> bool:
    return any(p.search(text) for p in patterns)


def _is_teacher_note(block: Block, config: dict,
                     is_structural_header: bool = False) -> bool:
    """
    Heurísticas para detectar teacher notes (cuadros laterales del profesor).
    """
    # Los headers estructurales (Unit X / Lesson X) NUNCA son teacher notes,
    # incluso si están en posición que parece sidebar.
    if is_structural_header:
        return False

    cfg = config["teacher_notes"]
    text = block.text.strip()

    # 1) Marcadores textuales explícitos en la primera línea
    first_line = text.split("\n", 1)[0].strip().lower()
    for marker in cfg["text_markers"]:
        if marker.lower() in first_line:
            return True

    # 2) Width ratio: notas suelen estar en columnas estrechas
    # Pero solo aplicamos esto si el bloque NO está en la primera mitad
    # vertical de la página (los headers a veces son cortos pero no son sidebars).
    if block.width_ratio > 0 and block.width_ratio <= cfg["sidebar_width_ratio_max"]:
        # Sidebar real: ancho estrecho Y posicionado a la derecha
        # (x0 > mitad de la página)
        if block.page_width > 0 and block.x0 > block.page_width * 0.5:
            if len(text) > 20:
                return True

    return False


def _is_section_header(block: Block, config: dict) -> str | None:
    """
    Si la primera línea matchea una keyword de sección funcional, devuelve
    la sección. Sino, None.

    Sección = Vocabulary, Grammar, Listening, etc.
    """
    first_line = block.text.split("\n", 1)[0].strip().lower()
    for section, keywords in config["section_keywords"].items():
        for kw in keywords:
            # Match al inicio de la línea, palabra completa
            if re.match(rf"^{re.escape(kw)}\b", first_line):
                return section
    return None


def _is_noise(block: Block, drop_patterns: list[re.Pattern],
              boilerplate: set[str]) -> bool:
    text = block.text.strip()
    # Línea entera coincide con boilerplate
    for line in text.split("\n"):
        if line.strip() in boilerplate:
            continue
        # Si quedan líneas no-boilerplate, no es noise
        if line.strip():
            break
    else:
        return True  # todas las líneas son boilerplate

    # Patrones de descarte
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if not _matches_any_pattern(line, drop_patterns):
            return False
    return True


def classify_block(block: Block, config: dict,
                   boilerplate: set[str],
                   drop_patterns: list[re.Pattern],
                   is_structural_header: bool = False) -> tuple[ContentType, dict]:
    """
    Clasifica un bloque en ContentType. Devuelve también metadata adicional
    (ej: el nombre de la sección si es header).

    Args:
        is_structural_header: True si el bloque ya fue identificado como
            inicio de Unit/Lesson por structure_detector. En ese caso, no se
            considera teacher_note ni section_header.
    """
    if _is_noise(block, drop_patterns, boilerplate):
        return ContentType.NOISE, {}

    if is_structural_header:
        # Es un header de Unit/Lesson; lo marcamos como section_header con su rol
        # (no debe duplicarse en el cuerpo del markdown porque el renderer
        # ya pone el ## Unit / ## Lesson aparte).
        return ContentType.NOISE, {}  # se omite del cuerpo

    section = _is_section_header(block, config)
    if section:
        return ContentType.SECTION_HEADER, {"section": section}

    if _is_teacher_note(block, config):
        return ContentType.TEACHER_NOTE, {}

    return ContentType.STUDENT_CONTENT, {}


def compile_drop_patterns(config: dict) -> list[re.Pattern]:
    return [re.compile(p) for p in config["noise"]["drop_line_patterns"]]
