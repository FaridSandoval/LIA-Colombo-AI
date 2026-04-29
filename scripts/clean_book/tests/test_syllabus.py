"""
Tests del módulo clean_book.

Ejecutar desde la raíz del proyecto:
    python -m pytest scripts/clean_book/tests/ -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.clean_book.syllabus import (
    Syllabus, UnitSpec, load_syllabus, VALID_CYCLES,
)
from scripts.clean_book.markdown_renderer import slugify


# Path al syllabus en el repo (data/raw/)
SYLLABUS_PATH = Path("data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx")


@pytest.mark.skipif(
    not SYLLABUS_PATH.exists(),
    reason=f"Syllabus no encontrado en {SYLLABUS_PATH}",
)
class TestSyllabusReal:
    """Tests con el archivo real del Colombo."""

    def setup_method(self):
        self.syllabus = load_syllabus(SYLLABUS_PATH)

    def test_loads_24_units(self):
        assert len(self.syllabus) == 24

    def test_has_both_cycles(self):
        for cycle in VALID_CYCLES:
            assert len(self.syllabus.units_for_cycle(cycle)) == 12, \
                f"{cycle} debería tener 12 unidades"

    def test_fundamental_plus_unit_1_is_extraordinary(self):
        spec = self.syllabus.get("Fundamental Plus", 1)
        assert spec is not None
        assert spec.name == "Extraordinary"
        assert "Past Progressive" in spec.grammar_1

    def test_fundamental_plus_unit_6_is_changes(self):
        spec = self.syllabus.get("Fundamental Plus", 6)
        assert spec is not None
        assert spec.name == "Changes"
        assert "Present Perfect" in spec.grammar_1

    def test_grammar_keywords_extracted(self):
        spec = self.syllabus.get("Fundamental Plus", 1)
        kws = spec.grammar_keywords
        assert "past" in kws
        assert "progressive" in kws

    def test_sample_questions_loaded(self):
        spec = self.syllabus.get("Fundamental Plus", 1)
        # Unit 1 de FP tiene 5 preguntas en el archivo real
        assert len(spec.sample_questions) == 5
        assert "favorite performer" in spec.sample_questions[0].lower()

    def test_unit_12_fp_has_4_questions(self):
        # Unit 12 tiene un NaN en la 5ta pregunta
        spec = self.syllabus.get("Fundamental Plus", 12)
        assert len(spec.sample_questions) == 4


class TestSyllabusErrors:
    """Tests de error paths sin depender del archivo real."""

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_syllabus(Path("/no/existe.xlsx"))


class TestSlugify:
    @pytest.mark.parametrize("inp,expected", [
        ("Extraordinary", "extraordinary"),
        ("What's Trending?", "whats_trending"),
        ("Use and Reuse", "use_and_reuse"),
        ("I'm a Member", "im_a_member"),
        ("Room for Me", "room_for_me"),
        ("", "untitled"),
        ("   ", "untitled"),
    ])
    def test_slugify(self, inp, expected):
        assert slugify(inp) == expected
