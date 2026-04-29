"""
Detección de estructura del libro a partir de los bloques crudos.

Identifica:
- Fronteras de Unit (header con número + nombre, posiblemente en bloques separados)
- Fronteras de Lesson
- Boilerplate a descartar
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .pdf_extractor import Block, PageContent
from .syllabus import Syllabus, UnitSpec

logger = logging.getLogger(__name__)


@dataclass
class UnitBoundary:
    page: int
    block_index: int
    unit_number: int
    title: str
    matched_pattern: str
    block: Block


@dataclass
class LessonBoundary:
    page: int
    block_index: int
    unit_number: int
    lesson_id: str
    title: str
    block: Block


@dataclass
class StructuredUnit:
    unit_number: int
    title: str
    blocks: list[Block] = field(default_factory=list)
    tables: list = field(default_factory=list)
    lessons: list[LessonBoundary] = field(default_factory=list)


def _compile_patterns(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.MULTILINE) for p in patterns]


def detect_unit_boundaries(
    pages: list[PageContent],
    config: dict,
    syllabus: Syllabus,
    cycle: str,
) -> list[UnitBoundary]:
    """
    Detecta los headers de Unit. Soporta DOS estilos:

    1) Header en un solo bloque: "Unit 1 — Extraordinary".
       Matchea con los patrones del YAML (unit_boundary.patterns).

    2) Header en DOS bloques en la MISMA página y cercanos verticalmente:
       primero un bloque con SOLO un número grande ("1", "2", ...) y luego
       un bloque con el nombre ("Extraordinary"). Estilo Speak Your Mind.

    Cruza con el syllabus para validar.
    """
    patterns = _compile_patterns(config["unit_boundary"]["patterns"])
    min_size = config["unit_boundary"]["min_font_size"]

    expected = {u.unit: u.name for u in syllabus.units_for_cycle(cycle)}
    expected_names_norm = {_norm(name): num for num, name in expected.items()}

    boundaries: list[UnitBoundary] = []

    # ---- Estilo 1: header en un solo bloque ----
    for page in pages:
        for idx, block in enumerate(page.blocks):
            if block.font_size < min_size:
                continue
            first_line = block.text.split("\n", 1)[0].strip()
            for pat in patterns:
                m = pat.match(first_line)
                if not m:
                    continue
                try:
                    unit_num = int(m.group(1))
                except (ValueError, IndexError):
                    continue
                if unit_num not in expected:
                    continue
                title = ""
                if m.lastindex and m.lastindex >= 2:
                    title = (m.group(2) or "").strip(" —-:")
                if not title:
                    title = expected[unit_num]

                boundaries.append(UnitBoundary(
                    page=block.page, block_index=idx,
                    unit_number=unit_num, title=title,
                    matched_pattern=pat.pattern, block=block,
                ))
                break

    # ---- Estilo 2: número grande + nombre en bloques contiguos ----
    # Para cada página, buscamos bloques que sean solo un número (1-12)
    # y un bloque cercano (debajo) cuyo texto matchee el nombre esperado.
    for page in pages:
        for idx, block in enumerate(page.blocks):
            if block.font_size < min_size:
                continue
            text = block.text.strip()
            # Match: o solo un número, O un número seguido del nombre en otra línea
            m_num = re.match(r"^(\d{1,2})(?:\s*\n\s*(.+))?$", text, re.DOTALL)
            if not m_num:
                continue
            try:
                unit_num = int(m_num.group(1))
            except ValueError:
                continue
            inline_name = (m_num.group(2) or "").strip() if m_num.lastindex >= 2 else ""
            if unit_num not in expected:
                continue

            # Buscar bloque acompañante en la misma página que matchee el nombre
            target_name = _norm(expected[unit_num])
            companion = None
            for j, other in enumerate(page.blocks):
                if j == idx:
                    continue
                # Cercanía vertical: el bloque del nombre debe estar cerca
                # del número (típicamente justo debajo)
                if abs(other.y0 - block.y1) > 80 and abs(other.y0 - block.y0) > 80:
                    continue
                other_norm = _norm(other.text.split("\n", 1)[0])
                # Match exacto o aproximado del nombre esperado
                if other_norm == target_name or _name_matches(other_norm, target_name):
                    companion = other
                    break

            # Si el bloque ya trae el nombre en una segunda línea, usar eso
            if inline_name and _name_matches(_norm(inline_name), _norm(expected[unit_num])):
                title = inline_name
            elif companion is not None:
                title = companion.text.split("\n", 1)[0].strip()
            else:
                # Fallback: solo aceptar si la página es razonable
                if block.page < 30:
                    continue
                title = expected[unit_num]

            boundaries.append(UnitBoundary(
                page=block.page, block_index=idx,
                unit_number=unit_num, title=title,
                matched_pattern="number+name (split)", block=block,
            ))

    # ---- Deduplicar: nos quedamos con la PRIMERA ocurrencia de cada Unit ----
    seen: dict[int, UnitBoundary] = {}
    for b in sorted(boundaries, key=lambda x: (x.page, x.block_index)):
        if b.unit_number not in seen:
            seen[b.unit_number] = b

    deduped = sorted(seen.values(), key=lambda x: x.unit_number)
    logger.info("Detectadas %d unidades únicas", len(deduped))
    for ub in deduped:
        logger.debug("  Unit %d (%r) en pág %d", ub.unit_number, ub.title, ub.page)
    return deduped


def _norm(s: str) -> str:
    """Normaliza un string para comparación: minúsculas, sin signos."""
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _name_matches(candidate: str, expected: str) -> bool:
    """Match aproximado: el candidato contiene todas las palabras del esperado."""
    if not candidate or not expected:
        return False
    cand_words = set(candidate.split())
    exp_words = set(expected.split())
    # ≥80% de las palabras esperadas presentes en el candidato
    if not exp_words:
        return False
    overlap = len(cand_words & exp_words) / len(exp_words)
    return overlap >= 0.8


def detect_lesson_boundaries(
    pages: list[PageContent],
    config: dict,
    unit_boundaries: list[UnitBoundary],
) -> list[LessonBoundary]:
    """Detecta lessons dentro del rango de cada Unit."""
    patterns = _compile_patterns(config["lesson_boundary"]["patterns"])
    min_size = config["lesson_boundary"]["min_font_size"]

    if not unit_boundaries:
        return []

    sorted_units = sorted(unit_boundaries, key=lambda u: (u.page, u.block_index))
    unit_ranges: list[tuple[int, int, int]] = []
    for i, ub in enumerate(sorted_units):
        next_page = sorted_units[i + 1].page if i + 1 < len(sorted_units) else 10**9
        unit_ranges.append((ub.unit_number, ub.page, next_page))

    def find_unit_for_page(page_num: int) -> Optional[int]:
        for unit_num, start, end in unit_ranges:
            if start <= page_num < end:
                return unit_num
        return None

    boundaries: list[LessonBoundary] = []
    for page in pages:
        for idx, block in enumerate(page.blocks):
            if block.font_size < min_size:
                continue
            unit_num = find_unit_for_page(block.page)
            if unit_num is None:
                continue
            first_line = block.text.split("\n", 1)[0].strip()
            for pat in patterns:
                m = pat.match(first_line)
                if not m:
                    continue
                lesson_id = ""
                title = ""
                groups = m.groups()
                if len(groups) >= 2:
                    if groups[1] and groups[1].isalpha():
                        lesson_id = f"{groups[0]}{groups[1].upper()}"
                        title = (groups[2] if len(groups) > 2 else "") or ""
                    else:
                        lesson_id = groups[0]
                        title = groups[1] or ""
                else:
                    lesson_id = groups[0]

                boundaries.append(LessonBoundary(
                    page=block.page, block_index=idx,
                    unit_number=unit_num,
                    lesson_id=lesson_id, title=title.strip(),
                    block=block,
                ))
                break
    logger.info("Detectadas %d lessons", len(boundaries))
    return boundaries


def slice_units(
    pages: list[PageContent],
    unit_boundaries: list[UnitBoundary],
    lesson_boundaries: list[LessonBoundary],
) -> list[StructuredUnit]:
    if not unit_boundaries:
        return []

    sorted_ubs = sorted(unit_boundaries, key=lambda u: (u.page, u.block_index))
    structured: list[StructuredUnit] = []

    for i, ub in enumerate(sorted_ubs):
        if i + 1 < len(sorted_ubs):
            end = (sorted_ubs[i + 1].page, sorted_ubs[i + 1].block_index)
        else:
            end = (10**9, 10**9)

        unit_blocks: list[Block] = []
        unit_tables = []
        for page in pages:
            for idx, block in enumerate(page.blocks):
                pos = (block.page, idx)
                start = (ub.page, ub.block_index)
                if start <= pos < end:
                    unit_blocks.append(block)
            for table in page.tables:
                if (table.page, 0) >= (ub.page, 0) and (table.page, 0) < (end[0], 0):
                    unit_tables.append(table)

        unit_lessons = [
            lb for lb in lesson_boundaries if lb.unit_number == ub.unit_number
        ]
        structured.append(StructuredUnit(
            unit_number=ub.unit_number,
            title=ub.title,
            blocks=unit_blocks,
            tables=unit_tables,
            lessons=unit_lessons,
        ))

    return structured


def detect_boilerplate(pages: list[PageContent], min_pages: int) -> set[str]:
    line_pages: dict[str, set[int]] = defaultdict(set)
    for page in pages:
        for block in page.blocks:
            for line in block.text.split("\n"):
                line = line.strip()
                if line and len(line) < 80:
                    line_pages[line].add(block.page)
    boilerplate = {line for line, pgs in line_pages.items()
                   if len(pgs) >= min_pages}
    logger.info("Detectadas %d líneas de boilerplate", len(boilerplate))
    return boilerplate