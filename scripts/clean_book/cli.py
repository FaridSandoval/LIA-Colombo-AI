"""
CLI del pipeline de limpieza.

Modos:
    1) Audit (--audit-only): inspecciona el PDF y propone heurísticas.
    2) Clean (default): ejecuta el pipeline completo y produce los .md.

Flags importantes:
    --strict / --permissive    Modo estricto (default) o permisivo.
    --cycle "Fundamental Plus" Cycle del syllabus a procesar.
    --pages 1-150              Subset de páginas del PDF (debug).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import yaml

from .audit import audit
from .content_classifier import classify_block, compile_drop_patterns
from .markdown_renderer import write_unit_file, ClassifiedBlock
from .pdf_extractor import extract_pdf
from .structure_detector import (
    detect_unit_boundaries, detect_lesson_boundaries,
    slice_units, detect_boilerplate,
)
from .syllabus import load_syllabus
from .validator import validate, ValidationError


def _setup_logging(verbosity: int) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _parse_pages(s: str | None) -> tuple[int, int] | None:
    if not s:
        return None
    if "-" not in s:
        n = int(s)
        return (n, n)
    a, b = s.split("-", 1)
    return (int(a), int(b))


def _load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="clean_book",
        description="Limpieza de Teacher's Edition PDF → Markdown estructurado",
    )
    parser.add_argument("--pdf", type=Path, required=True,
                        help="Path al PDF (Teacher's Edition)")
    parser.add_argument("--syllabus", type=Path, required=True,
                        help="Path al Syllabus_Guide_-_Scope_and_Sequence.xlsx")
    parser.add_argument("--config", type=Path,
                        default=Path(__file__).parent / "configs" /
                        "speak_your_mind_2.yaml",
                        help="YAML con heurísticas del libro")
    parser.add_argument("--cycle", default="Fundamental Plus",
                        choices=["Fundamental", "Fundamental Plus"],
                        help="Cycle del syllabus a procesar")
    parser.add_argument("--out", type=Path, default=Path("data/raw"),
                        help="Carpeta donde escribir los .md")
    parser.add_argument("--audit-only", action="store_true",
                        help="Solo genera reporte de auditoría, no produce .md")
    parser.add_argument("--strict", dest="strict", action="store_true",
                        default=True,
                        help="Modo estricto: falla si validación no cumple (default)")
    parser.add_argument("--permissive", dest="strict", action="store_false",
                        help="Modo permisivo: warnings en vez de errores")
    parser.add_argument("--pages", type=str, default=None,
                        help="Rango de páginas (ej. '1-50'); útil para debug")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Aumentar verbosidad (-v info, -vv debug)")
    args = parser.parse_args()

    _setup_logging(args.verbose)
    log = logging.getLogger("clean_book.cli")

    # Cargar config y syllabus
    config = _load_config(args.config)
    syllabus = load_syllabus(args.syllabus)

    # Validar que el cycle exista en el syllabus
    cycle_units = syllabus.units_for_cycle(args.cycle)
    if not cycle_units:
        log.error("Cycle '%s' no tiene unidades en el syllabus.", args.cycle)
        return 2
    log.info("Cycle '%s': %d unidades esperadas", args.cycle, len(cycle_units))

    # Extracción cruda
    page_range = _parse_pages(args.pages)
    pages = extract_pdf(
        args.pdf,
        table_settings=config["tables"]["extract_settings"],
        page_range=page_range,
    )

    # Modo audit
    if args.audit_only:
        audit(pages, args.out)
        log.info("Audit completado. Ajusta el YAML si es necesario y vuelve a correr.")
        return 0

    # Detección de estructura
    boilerplate = detect_boilerplate(
        pages, min_pages=config["noise"]["repeated_line_min_pages"],
    )
    drop_patterns = compile_drop_patterns(config)

    unit_boundaries = detect_unit_boundaries(pages, config, syllabus, args.cycle)
    if not unit_boundaries:
        log.error("No se detectaron unidades en el PDF. "
                  "Corre con --audit-only y ajusta el YAML.")
        return 3
    lesson_boundaries = detect_lesson_boundaries(pages, config, unit_boundaries)
    units = slice_units(pages, unit_boundaries, lesson_boundaries)

    # Validación contra el syllabus
    try:
        report = validate(units, syllabus, args.cycle, strict=args.strict)
    except ValidationError as e:
        print(str(e), file=sys.stderr)
        return 4

    # Clasificar bloques y renderizar
    args.out.mkdir(parents=True, exist_ok=True)

    # Identificar bloques que son headers estructurales (Unit/Lesson)
    structural_block_ids: set[int] = set()
    for ub in unit_boundaries:
        structural_block_ids.add(id(ub.block))
    for lb in lesson_boundaries:
        structural_block_ids.add(id(lb.block))

    for unit in units:
        spec = syllabus.get(args.cycle, unit.unit_number)
        if spec is None:
            log.warning("Unit %d no está en el syllabus para cycle '%s'; se omite.",
                        unit.unit_number, args.cycle)
            continue

        classified: list[ClassifiedBlock] = []
        for block in unit.blocks:
            ct, extra = classify_block(
                block, config, boilerplate, drop_patterns,
                is_structural_header=id(block) in structural_block_ids,
            )
            classified.append(ClassifiedBlock(
                block=block, content_type=ct, extra=extra,
            ))

        write_unit_file(
            unit=unit,
            classified_blocks=classified,
            spec=spec,
            out_dir=args.out,
            config=config,
            source_pdf=args.pdf.name,
        )

    log.info("Pipeline completado. Salida en: %s", args.out)
    print(report.summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
