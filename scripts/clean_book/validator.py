"""
Validación post-limpieza: cruza la salida con el syllabus para confirmar
que la limpieza preservó la estructura curricular esperada.

Modo estricto: lanza ValidationError si algo no cumple.
Modo permisivo: solo loguea warnings.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .structure_detector import StructuredUnit
from .syllabus import Syllabus, UnitSpec

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    pass


@dataclass
class ValidationReport:
    cycle: str
    expected_units: int
    found_units: int
    missing_units: list[int] = field(default_factory=list)
    extra_units: list[int] = field(default_factory=list)
    grammar_mismatch: list[str] = field(default_factory=list)
    empty_units: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(
            self.missing_units or self.empty_units or self.grammar_mismatch
        )

    def summary(self) -> str:
        lines = [
            f"=== Validation Report — {self.cycle} ===",
            f"Expected units: {self.expected_units}",
            f"Found units: {self.found_units}",
        ]
        if self.missing_units:
            lines.append(f"❌ Missing units: {self.missing_units}")
        if self.extra_units:
            lines.append(f"⚠ Extra units (not in syllabus): {self.extra_units}")
        if self.empty_units:
            lines.append(f"❌ Empty units (no blocks): {self.empty_units}")
        if self.grammar_mismatch:
            lines.append(f"❌ Grammar mismatches:")
            for m in self.grammar_mismatch:
                lines.append(f"    {m}")
        if self.warnings:
            lines.append(f"⚠ Warnings ({len(self.warnings)}):")
            for w in self.warnings[:10]:
                lines.append(f"    {w}")
            if len(self.warnings) > 10:
                lines.append(f"    ... y {len(self.warnings) - 10} más")
        if not self.has_errors:
            lines.append("✅ Validación OK")
        return "\n".join(lines)


def validate(
    units: list[StructuredUnit],
    syllabus: Syllabus,
    cycle: str,
    strict: bool,
) -> ValidationReport:
    expected = syllabus.units_for_cycle(cycle)
    expected_nums = {u.unit for u in expected}
    found_nums = {u.unit_number for u in units}

    report = ValidationReport(
        cycle=cycle,
        expected_units=len(expected),
        found_units=len(units),
        missing_units=sorted(expected_nums - found_nums),
        extra_units=sorted(found_nums - expected_nums),
    )

    # Empty units
    for unit in units:
        if not unit.blocks:
            report.empty_units.append(unit.unit_number)

    # Grammar/Vocabulary keyword check: el texto de la unidad debe contener al menos
    # uno de los términos clave de cada gramática esperada.
    units_by_num = {u.unit_number: u for u in units}
    for spec in expected:
        if spec.unit not in units_by_num:
            continue
        unit_text = "\n".join(
            b.text for b in units_by_num[spec.unit].blocks
        ).lower()
        for grammar_topic in [spec.grammar_1, spec.grammar_2]:
            keywords = _significant_tokens(grammar_topic)
            if not keywords:
                continue
            hits = sum(1 for k in keywords if k.lower() in unit_text)
            if hits == 0:
                report.grammar_mismatch.append(
                    f"Unit {spec.unit} ({spec.name}): no se encontraron términos "
                    f"de '{grammar_topic}' (esperaba al menos uno de: {keywords})"
                )

    msg = report.summary()
    if report.has_errors and strict:
        logger.error(msg)
        raise ValidationError(
            "Validación falló en modo estricto. "
            "Usa --permissive para forzar la salida.\n" + msg
        )
    if report.has_errors:
        logger.warning(msg)
    else:
        logger.info(msg)
    return report


def _significant_tokens(topic: str) -> set[str]:
    """Tokens 'gramaticalmente significativos' del nombre de un topic."""
    stop = {"and", "or", "the", "a", "an", "of", "with", "for", "as",
            "vs", "vs.", "no", "not", "in", "on", "to", "be", "are"}
    tokens = re.findall(r"[A-Za-z']{3,}", topic)
    return {t for t in tokens if t.lower() not in stop}
