"""
Cambio B del fix F6 - Amplia _OFF_DOMAIN_HINTS en src/guardrails.py
con variantes verbales y temas adicionales para que la heuristica
detecte off-domain antes de llegar al modo degradado.

Uso:
    python tools/update_guardrails_b.py

Antes de correr, asegurate de tener el backup:
    src/guardrails.py.pre_f6_fix
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


NEW_OFF_DOMAIN_BLOCK = '''_OFF_DOMAIN_HINTS = {
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
}'''


def main() -> int:
    guardrails_path = Path("src/guardrails.py")
    backup_path = Path("src/guardrails.py.pre_f6_fix")

    if not guardrails_path.exists():
        print(f"ERROR: No encuentro {guardrails_path}. Estas en la raiz del proyecto?")
        return 1

    if not backup_path.exists():
        print(f"ERROR: No existe el backup {backup_path}.")
        return 1

    text = guardrails_path.read_text(encoding="utf-8")

    # Patron: encuentra la asignacion completa de _OFF_DOMAIN_HINTS
    # incluyendo el bloque entre llaves (puede tener saltos de linea).
    pattern = re.compile(
        r'_OFF_DOMAIN_HINTS\s*=\s*\{[\s\S]*?\}',
        re.MULTILINE,
    )

    matches = pattern.findall(text)
    if len(matches) == 0:
        print("ERROR: No se encontro _OFF_DOMAIN_HINTS en src/guardrails.py.")
        return 2
    if len(matches) > 1:
        print(f"ERROR: Se encontraron {len(matches)} ocurrencias.")
        return 3

    print("Set encontrado.")
    print(f"Tamano viejo: {len(matches[0])} caracteres")
    print(f"Tamano nuevo: {len(NEW_OFF_DOMAIN_BLOCK)} caracteres")
    print()

    new_text = pattern.sub(NEW_OFF_DOMAIN_BLOCK, text, count=1)

    if new_text == text:
        print("ERROR: El reemplazo no cambio nada.")
        return 4

    guardrails_path.write_text(new_text, encoding="utf-8")
    print(f"OK: src/guardrails.py actualizado.")
    print(f"Backup intacto en: {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
