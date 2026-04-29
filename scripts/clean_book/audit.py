"""
Audit del PDF: genera un reporte que permite calibrar las heurísticas en YAML
ANTES de correr el pipeline completo de limpieza.

Uso interno: invocado desde cli.py con --audit-only.
Salida: reporte JSON + impresión humana.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from .pdf_extractor import PageContent

logger = logging.getLogger(__name__)


def audit(pages: list[PageContent], out_dir: Path) -> dict:
    """
    Genera un reporte estadístico del PDF crudo.
    Útil para decidir thresholds de font size en el YAML.
    """
    n_pages = len(pages)
    n_blocks = sum(len(p.blocks) for p in pages)
    n_tables = sum(len(p.tables) for p in pages)

    font_sizes: list[float] = []
    font_names: Counter = Counter()
    width_ratios: list[float] = []
    bold_count = 0
    italic_count = 0

    repeated_lines: dict[str, set[int]] = defaultdict(set)
    candidate_unit_lines: list[tuple[int, str, float]] = []
    candidate_lesson_lines: list[tuple[int, str, float]] = []

    for page in pages:
        for b in page.blocks:
            font_sizes.append(b.font_size)
            font_names[b.font_name] += 1
            width_ratios.append(b.width_ratio)
            if b.is_bold:
                bold_count += 1
            if b.is_italic:
                italic_count += 1
            # Para repeated_lines: solo primera línea del bloque
            first_line = b.text.split("\n", 1)[0].strip()
            if first_line and len(first_line) < 80:
                repeated_lines[first_line].add(b.page)

            # Candidatos a header de Unit/Lesson por keyword + font grande
            text_lc = b.text.lower()
            if "unit " in text_lc and b.font_size > 14:
                candidate_unit_lines.append(
                    (b.page, b.text[:80], b.font_size)
                )
            if "lesson " in text_lc and b.font_size > 11:
                candidate_lesson_lines.append(
                    (b.page, b.text[:80], b.font_size)
                )

    # Boilerplate: líneas que aparecen en muchas páginas
    boilerplate = sorted(
        ((line, len(pages_set)) for line, pages_set in repeated_lines.items()
         if len(pages_set) >= 3),
        key=lambda x: -x[1],
    )[:30]

    # Estadísticas de font sizes
    font_sizes_sorted = sorted(font_sizes)
    p10 = font_sizes_sorted[len(font_sizes_sorted) // 10] if font_sizes else 0
    p50 = font_sizes_sorted[len(font_sizes_sorted) // 2] if font_sizes else 0
    p90 = font_sizes_sorted[(9 * len(font_sizes_sorted)) // 10] if font_sizes else 0
    p99 = font_sizes_sorted[(99 * len(font_sizes_sorted)) // 100] if font_sizes else 0
    max_size = max(font_sizes) if font_sizes else 0
    min_size = min(font_sizes) if font_sizes else 0

    report = {
        "summary": {
            "n_pages": n_pages,
            "n_blocks": n_blocks,
            "n_tables": n_tables,
            "blocks_per_page_mean": round(n_blocks / max(n_pages, 1), 2),
            "bold_ratio": round(bold_count / max(n_blocks, 1), 3),
            "italic_ratio": round(italic_count / max(n_blocks, 1), 3),
        },
        "font_size_distribution": {
            "min": round(min_size, 2),
            "p10": round(p10, 2),
            "p50_median": round(p50, 2),
            "p90": round(p90, 2),
            "p99": round(p99, 2),
            "max": round(max_size, 2),
            "recommendation": _font_size_recommendation(p50, p90, p99, max_size),
        },
        "top_fonts": font_names.most_common(10),
        "candidate_unit_headers": candidate_unit_lines[:30],
        "candidate_lesson_headers": candidate_lesson_lines[:30],
        "likely_boilerplate": boilerplate,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "audit_report.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    logger.info("Reporte de auditoría escrito en %s", out_file)
    _print_human_summary(report)
    return report


def _font_size_recommendation(p50: float, p90: float, p99: float,
                              max_size: float) -> dict:
    """Sugiere thresholds para el YAML."""
    return {
        "body_text_size_estimate": round(p50, 1),
        "lesson_header_min_estimate": round(p90, 1),
        "unit_header_min_estimate": round((p99 + max_size) / 2, 1),
        "comment": (
            "Si los headers detectados son muy pocos, baja unit_header_min. "
            "Si capturan texto del cuerpo, súbelo. p99 suele ser un buen punto "
            "de partida para 'lesson'; (p99+max)/2 para 'unit'."
        ),
    }


def _print_human_summary(report: dict) -> None:
    print("\n" + "=" * 60)
    print("AUDIT REPORT — Speak Your Mind 2 Teacher's Edition")
    print("=" * 60)
    s = report["summary"]
    print(f"Páginas: {s['n_pages']}")
    print(f"Bloques: {s['n_blocks']} (promedio {s['blocks_per_page_mean']}/pág)")
    print(f"Tablas detectadas: {s['n_tables']}")
    print(f"Ratio bold: {s['bold_ratio']:.1%} | italic: {s['italic_ratio']:.1%}")

    fs = report["font_size_distribution"]
    print(f"\nDistribución de font size:")
    print(f"  min={fs['min']} | p50={fs['p50_median']} | p90={fs['p90']} "
          f"| p99={fs['p99']} | max={fs['max']}")
    rec = fs["recommendation"]
    print(f"\nSugerencia para YAML:")
    print(f"  body text estimado: {rec['body_text_size_estimate']}pt")
    print(f"  lesson_header min:  {rec['lesson_header_min_estimate']}pt")
    print(f"  unit_header min:    {rec['unit_header_min_estimate']}pt")

    print(f"\nTop fonts:")
    for font, n in report["top_fonts"][:5]:
        print(f"  {n:>6}  {font}")

    if report["candidate_unit_headers"]:
        print(f"\nCandidatos a 'Unit X' headers (primeros 10):")
        for page, text, size in report["candidate_unit_headers"][:10]:
            print(f"  pág {page:>3} | {size:>5.1f}pt | {text!r}")

    if report["likely_boilerplate"]:
        print(f"\nBoilerplate probable (primeros 5):")
        for line, n_pages in report["likely_boilerplate"][:5]:
            print(f"  apareció en {n_pages:>3} págs: {line!r}")

    print("=" * 60 + "\n")
