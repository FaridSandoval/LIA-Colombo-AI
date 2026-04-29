"""
Convierte una `StructuredUnit` clasificada en un archivo Markdown.

Estructura de salida:
- YAML frontmatter con metadata (cycle, unit, level, grammar, vocabulary).
- Header `# Unit N — Title`.
- Subsecciones por Lesson (`## Lesson 1A — Heroes`).
- Dentro de cada Lesson, subsecciones por sección funcional
  (`### Vocabulary`, `### Grammar`, etc.).
- Teacher Notes en bloques separados con `### Teacher Notes`.
- Tablas se preservan como Markdown tables.
- TODOs marcados donde haya inconsistencias.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .content_classifier import ContentType
from .pdf_extractor import Block, Table
from .structure_detector import StructuredUnit, LessonBoundary
from .syllabus import UnitSpec

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedBlock:
    """Bloque ya clasificado por content_classifier."""
    block: Block
    content_type: ContentType
    extra: dict = field(default_factory=dict)


def slugify(text: str) -> str:
    """Convierte un título en un slug seguro para nombre de archivo."""
    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s-]+", "_", s).strip("_")
    return s or "untitled"


def _table_to_markdown(table: Table) -> str:
    """Convierte una tabla pdfplumber a Markdown table."""
    rows = table.cells
    if not rows:
        return ""
    # Limpiar Nones y normalizar
    cleaned = [[(c or "").strip().replace("\n", " ") for c in row]
               for row in rows]
    # Filtrar filas completamente vacías
    cleaned = [r for r in cleaned if any(c for c in r)]
    if len(cleaned) < 2:
        return ""

    # Ancho consistente
    max_cols = max(len(r) for r in cleaned)
    cleaned = [r + [""] * (max_cols - len(r)) for r in cleaned]

    header = cleaned[0]
    body = cleaned[1:]
    md = "| " + " | ".join(header) + " |\n"
    md += "|" + "|".join(["---"] * max_cols) + "|\n"
    for row in body:
        md += "| " + " | ".join(row) + " |\n"
    return md


def _frontmatter(spec: UnitSpec, title: str, source_pdf: str) -> str:
    """Genera YAML frontmatter para el documento Markdown."""
    return (
        "---\n"
        f"cycle: {spec.cycle}\n"
        f"unit: {spec.unit}\n"
        f"unit_name: {title}\n"
        f"grammar:\n"
        f"  - {spec.grammar_1}\n"
        f"  - {spec.grammar_2}\n"
        f"vocabulary:\n"
        f"  - {spec.vocabulary_1}\n"
        f"  - {spec.vocabulary_2}\n"
        f"  - {spec.vocabulary_3}\n"
        f"source_pdf: {source_pdf}\n"
        f"source_type: book\n"
        "---\n\n"
    )


def render_unit_markdown(
    unit: StructuredUnit,
    classified_blocks: list[ClassifiedBlock],
    spec: UnitSpec,
    source_pdf: str,
    todo_marker: str,
) -> str:
    """
    Compone el Markdown de una unidad. Mantiene orden de aparición de bloques
    pero AGRUPA teacher_notes al final de cada lesson.
    """
    md_parts: list[str] = [_frontmatter(spec, unit.title, source_pdf)]
    md_parts.append(f"# Unit {unit.unit_number} — {unit.title}\n\n")

    # Ordenar lessons por (page, block_index)
    sorted_lessons = sorted(unit.lessons, key=lambda l: (l.page, l.block_index))

    if not sorted_lessons:
        md_parts.append(
            f"{todo_marker} no se detectaron Lessons en esta unidad. "
            f"Revisar PDF manualmente.\n\n"
        )
        # Volcar todos los bloques sin estructura de lessons
        md_parts.append(_render_block_sequence(classified_blocks, todo_marker))
        return "".join(md_parts)

    # Computar rangos por lesson
    lesson_ranges: list[tuple[LessonBoundary, tuple[int, int], tuple[int, int]]] = []
    for i, lesson in enumerate(sorted_lessons):
        start = (lesson.page, lesson.block_index)
        if i + 1 < len(sorted_lessons):
            end = (sorted_lessons[i + 1].page, sorted_lessons[i + 1].block_index)
        else:
            end = (10**9, 10**9)
        lesson_ranges.append((lesson, start, end))

    # Bloques antes del primer lesson (intro de unidad)
    if lesson_ranges:
        first_start = lesson_ranges[0][1]
        intro_blocks = [
            cb for cb in classified_blocks
            if (cb.block.page, _block_idx(cb.block, classified_blocks)) < first_start
        ]
        if intro_blocks:
            md_parts.append("## Introducción de la unidad\n\n")
            md_parts.append(_render_block_sequence(intro_blocks, todo_marker))

    # Bloques por lesson
    for lesson, start, end in lesson_ranges:
        title = f"Lesson {lesson.lesson_id}"
        if lesson.title:
            title += f" — {lesson.title}"
        md_parts.append(f"\n## {title}\n\n")

        lesson_cbs = [
            cb for cb in classified_blocks
            if start <= (cb.block.page, _block_idx(cb.block, classified_blocks)) < end
        ]
        md_parts.append(_render_block_sequence(lesson_cbs, todo_marker))

    return "".join(md_parts)


def _block_idx(block: Block, classified_blocks: list[ClassifiedBlock]) -> int:
    """Helper: índice del bloque dentro de los classified, para comparar."""
    for i, cb in enumerate(classified_blocks):
        if cb.block is block:
            return i
    return 0


def _render_block_sequence(cbs: list[ClassifiedBlock], todo_marker: str) -> str:
    """
    Renderiza una secuencia de bloques manteniendo su orden,
    pero agrupando los teacher_notes al final.
    """
    student_parts: list[str] = []
    teacher_parts: list[str] = []
    current_section: str | None = None

    for cb in cbs:
        block = cb.block
        ct = cb.content_type
        text = block.text.strip()

        if ct == ContentType.NOISE:
            continue

        if ct == ContentType.SECTION_HEADER:
            section = cb.extra.get("section", "section").title()
            current_section = section
            student_parts.append(f"\n### {section}\n\n")
            # Si hay más texto en el bloque después del header, incluirlo
            extra_lines = text.split("\n", 1)[1:] if "\n" in text else []
            if extra_lines and extra_lines[0].strip():
                student_parts.append(extra_lines[0].strip() + "\n\n")
            continue

        if ct == ContentType.TEACHER_NOTE:
            teacher_parts.append(text + "\n\n")
            continue

        # STUDENT_CONTENT
        student_parts.append(text + "\n\n")

    out = "".join(student_parts)
    if teacher_parts:
        out += "\n### Teacher Notes\n\n"
        out += "".join(teacher_parts)
    return out


def write_unit_file(
    unit: StructuredUnit,
    classified_blocks: list[ClassifiedBlock],
    spec: UnitSpec,
    out_dir: Path,
    config: dict,
    source_pdf: str,
) -> Path:
    """Escribe el archivo Markdown de una unidad."""
    template = config["output"]["filename_template"]
    todo_marker = config["output"]["todo_marker"]
    filename = template.format(
        unit=unit.unit_number,
        slug=slugify(unit.title or spec.name),
    )
    md = render_unit_markdown(
        unit=unit, classified_blocks=classified_blocks,
        spec=spec, source_pdf=source_pdf, todo_marker=todo_marker,
    )
    out_path = out_dir / filename
    out_path.write_text(md, encoding="utf-8")
    logger.info("Escrito: %s (%d bloques, %d teacher_notes)",
                out_path,
                sum(1 for cb in classified_blocks
                    if cb.content_type == ContentType.STUDENT_CONTENT),
                sum(1 for cb in classified_blocks
                    if cb.content_type == ContentType.TEACHER_NOTE))
    return out_path
