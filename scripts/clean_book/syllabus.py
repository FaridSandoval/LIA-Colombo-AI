"""
Carga, valida e indexa el Syllabus Guide (Scope and Sequence) en memoria.

El syllabus es la **fuente de verdad** para validar la limpieza del PDF:
si dice que Unit 6 de Fundamental Plus se llama "Changes" y cubre Present Perfect,
el script DEBE encontrar esos elementos en el PDF.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Cycles válidos según el archivo institucional
VALID_CYCLES = ("Fundamental", "Fundamental Plus")


@dataclass(frozen=True)
class UnitSpec:
    """Spec de una unidad según el syllabus."""

    cycle: str
    unit: int
    name: str
    grammar_1: str
    grammar_2: str
    vocabulary_1: str
    vocabulary_2: str
    vocabulary_3: str
    sample_questions: tuple[str, ...]

    @property
    def grammar_topics(self) -> tuple[str, str]:
        return (self.grammar_1, self.grammar_2)

    @property
    def vocabulary_topics(self) -> tuple[str, str, str]:
        return (self.vocabulary_1, self.vocabulary_2, self.vocabulary_3)

    @property
    def grammar_keywords(self) -> set[str]:
        """
        Tokens significativos de los topics gramaticales, para validación.
        Ej: "Past Progressive" → {"past", "progressive"}.
        """
        text = f"{self.grammar_1} {self.grammar_2}".lower()
        # Filtramos stopwords mínimas; queremos los términos gramaticales
        stop = {"and", "or", "the", "a", "an", "of", "with", "for", "as", "vs",
                "vs.", "no", "not", "in", "on", "to", "be"}
        tokens = re.findall(r"[a-zA-Z']+", text)
        return {t for t in tokens if t not in stop and len(t) > 1}


@dataclass
class Syllabus:
    """Syllabus completo, indexado para consulta rápida."""

    units: dict[tuple[str, int], UnitSpec] = field(default_factory=dict)

    def get(self, cycle: str, unit: int) -> Optional[UnitSpec]:
        return self.units.get((cycle, unit))

    def units_for_cycle(self, cycle: str) -> list[UnitSpec]:
        return sorted(
            (s for (c, _), s in self.units.items() if c == cycle),
            key=lambda u: u.unit,
        )

    def unit_names_for_cycle(self, cycle: str) -> list[str]:
        return [u.name for u in self.units_for_cycle(cycle)]

    def __len__(self) -> int:
        return len(self.units)


def load_syllabus(xlsx_path: Path) -> Syllabus:
    """
    Carga el Excel del syllabus y devuelve un objeto Syllabus.

    Lanza ValueError si el archivo no tiene la estructura esperada.
    """
    if not xlsx_path.exists():
        raise FileNotFoundError(f"Syllabus no encontrado: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    expected_cols = {
        "Cycle", "Unit", "Name",
        "Grammar 1", "Grammar 2",
        "Vocabulary 1", "Vocabulary 2", "Vocabulary 3",
        "Sample question 1", "Sample question 2", "Sample question 3",
        "Sample question 4", "Sample question 5",
    }
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(
            f"Columnas faltantes en syllabus: {missing}. "
            f"Encontradas: {list(df.columns)}"
        )

    syllabus = Syllabus()
    for _, row in df.iterrows():
        cycle = str(row["Cycle"]).strip()
        if cycle not in VALID_CYCLES:
            logger.warning(
                "Cycle desconocido '%s' en fila Unit=%s; se ignora.",
                cycle, row["Unit"],
            )
            continue

        try:
            unit_num = int(row["Unit"])
        except (TypeError, ValueError):
            logger.warning("Unit no numérico en cycle=%s: %s", cycle, row["Unit"])
            continue

        questions = tuple(
            str(row[f"Sample question {i}"]).strip()
            for i in range(1, 6)
            if pd.notna(row[f"Sample question {i}"])
        )

        spec = UnitSpec(
            cycle=cycle,
            unit=unit_num,
            name=str(row["Name"]).strip(),
            grammar_1=str(row["Grammar 1"]).strip(),
            grammar_2=str(row["Grammar 2"]).strip(),
            vocabulary_1=str(row["Vocabulary 1"]).strip(),
            vocabulary_2=str(row["Vocabulary 2"]).strip(),
            vocabulary_3=str(row["Vocabulary 3"]).strip(),
            sample_questions=questions,
        )
        syllabus.units[(cycle, unit_num)] = spec

    if not syllabus.units:
        raise ValueError("Syllabus cargado pero quedó vacío. Revisa el Excel.")

    logger.info("Syllabus cargado: %d unidades.", len(syllabus))
    return syllabus
