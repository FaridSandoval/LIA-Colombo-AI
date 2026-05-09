"""
Fix C v3 - Cambiar matching de subcadena a word boundaries en
heuristic_domain_check de src/guardrails.py.

Bug que arregla: la palabra "pasta" matcheaba "past" del set ESL.

Esta version evita problemas de escape de \b usando base64 para embeber
el codigo nuevo. Es mas feo pero 100% confiable.

Uso:
    python tools/update_guardrails_c.py
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path


# Codigo nuevo de la funcion heuristic_domain_check.
# Embebido en base64 para evitar problemas con \b en re.sub.
NEW_FUNCTION_B64 = (
    "ZGVmIGhldXJpc3RpY19kb21haW5fY2hlY2socXVlcnk6IHN0cikgLT4gc3RyOgogICAgIiIiQ2xhc2lmaWNhY2lvbiBiYXJhdGEgcG9yIGtleXdvcmRzLiBEZXZ1ZWx2ZSBJTl9ET01BSU4sIE9GRl9ET01BSU4gbyBVTktOT1dOLgoKICAgIFVzYSB3b3JkIGJvdW5kYXJpZXMgcGFyYSBldml0YXIgZmFsc29zIHBvc2l0aXZvcyBwb3Igc3ViY2FkZW5hLgogICAgRWplbXBsbzogInBhc3RhIiBOTyBkZWJlIG1hdGNoZWFyICJwYXN0Ii4KICAgICIiIgogICAgcSA9IHF1ZXJ5Lmxvd2VyKCkKCiAgICAjIE1hdGNoIGRlIGNhcmFjdGVyZXMgZGVsIGFsZmFiZXRvIGluZ2xlcyBlbWJlYmlkb3MgZW4gY29taWxsYXMgLT4gbXV5IHByb2JhYmxlIEVTTAogICAgaWYgcmUuc2VhcmNoKHIiWydcIl1bYS16QS1aIF0rWydcIl0iLCBxdWVyeSk6CiAgICAgICAgcmV0dXJuICJJTl9ET01BSU4iCgogICAgZGVmIF9jb3VudF93b3JkX21hdGNoZXModGV4dDogc3RyLCBrZXl3b3JkcykgLT4gaW50OgogICAgICAgIG4gPSAwCiAgICAgICAgZm9yIGt3IGluIGtleXdvcmRzOgogICAgICAgICAgICAjIHJlLmVzY2FwZSBwcm90ZWdlIGNhcmFjdGVyZXMgZXNwZWNpYWxlczsgd29yZCBib3VuZGFyaWVzIGV2aXRhbiBmYWxzb3MgcG9zaXRpdm9zCiAgICAgICAgICAgIHBhdHRlcm4gPSByIlxiIiArIHJlLmVzY2FwZShrdykgKyByIlxiIgogICAgICAgICAgICBpZiByZS5zZWFyY2gocGF0dGVybiwgdGV4dCk6CiAgICAgICAgICAgICAgICBuICs9IDEKICAgICAgICByZXR1cm4gbgoKICAgIG9mZiA9IF9jb3VudF93b3JkX21hdGNoZXMocSwgX09GRl9ET01BSU5fSElOVFMpCiAgICBlc2wgPSBfY291bnRfd29yZF9tYXRjaGVzKHEsIF9FU0xfS0VZV09SRFMpCgogICAgaWYgb2ZmID4gMCBhbmQgZXNsID09IDA6CiAgICAgICAgcmV0dXJuICJPRkZfRE9NQUlOIgogICAgaWYgZXNsID49IDE6CiAgICAgICAgcmV0dXJuICJJTl9ET01BSU4iCiAgICByZXR1cm4gIlVOS05PV04iCg=="
)


def main() -> int:
    guardrails_path = Path("src/guardrails.py")
    backup_path = Path("src/guardrails.py.pre_f6_fix")

    if not guardrails_path.exists():
        print(f"ERROR: No encuentro {guardrails_path}.")
        return 1
    if not backup_path.exists():
        print(f"ERROR: No existe el backup {backup_path}.")
        return 1

    # Decodificar el codigo nuevo
    new_function = base64.b64decode(NEW_FUNCTION_B64).decode("utf-8")
    print("Funcion nueva decodificada. Primeras 200 chars:")
    print(new_function[:200])
    print("...")
    print()

    text = guardrails_path.read_text(encoding="utf-8")

    pattern = re.compile(
        r'def heuristic_domain_check\(query: str\) -> str:[\s\S]*?(?=\ndef is_in_domain)',
        re.MULTILINE,
    )

    matches = pattern.findall(text)
    if len(matches) == 0:
        print("ERROR: No se encontro la funcion heuristic_domain_check.")
        return 2
    if len(matches) > 1:
        print(f"ERROR: Se encontraron {len(matches)} ocurrencias.")
        return 3

    print(f"Tamano viejo: {len(matches[0])} caracteres")
    print(f"Tamano nuevo: {len(new_function)} caracteres")
    print()

    # IMPORTANTE: usar lambda para evitar que re.sub interprete \b como backspace
    new_text = pattern.sub(lambda m: new_function + "\n", text, count=1)

    if new_text == text:
        print("ERROR: El reemplazo no cambio nada.")
        return 4

    guardrails_path.write_text(new_text, encoding="utf-8")
    print(f"OK: src/guardrails.py actualizado.")

    # Verificacion automatica
    print()
    print("Verificacion automatica:")
    sys.path.insert(0, ".")
    if "src.guardrails" in sys.modules:
        del sys.modules["src.guardrails"]
    try:
        from src.guardrails import heuristic_domain_check
    except Exception as e:
        print(f"  WARN: no se pudo importar para verificar: {e}")
        return 0

    test_cases = [
        # Caso principal del fix: pasta NO debe matchear past
        ("Como cocino pasta carbonara?", "OFF_DOMAIN"),
        # Casos ESL que deben seguir funcionando bien
        ("Cual es la diferencia entre past simple y present perfect?", "IN_DOMAIN"),
        ("Que significa la palabra house?", "IN_DOMAIN"),
        ("Como uso el verbo to be?", "IN_DOMAIN"),
        # Caso UNKNOWN: pregunta sin keywords claras
        ("Cual es el plural de child?", "UNKNOWN"),
        # Caso off-domain con tematica clara
        ("Tengo enfermedad y necesito tratamiento", "OFF_DOMAIN"),
    ]
    all_ok = True
    for q, expected in test_cases:
        actual = heuristic_domain_check(q)
        ok = actual == expected
        all_ok = all_ok and ok
        symbol = "OK  " if ok else "FAIL"
        print(f"  [{symbol}] esperado={expected:11s} | obtuvo={actual:11s} | {q!r}")
    print()
    if all_ok:
        print("Todos los tests pasaron.")
        return 0
    else:
        print("ALGUN TEST FALLO. Revisar el archivo modificado.")
        return 5


if __name__ == "__main__":
    sys.exit(main())
