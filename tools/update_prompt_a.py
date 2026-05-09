"""
Cambio A del fix F6 — Reemplaza DEGRADED_RESPONSE_SYSTEM_PROMPT en src/prompts.py
por una version reforzada con PASO 0 (rechazo off-domain antes que nada).

Uso:
    python tools/update_prompt_a.py

Antes de correr, asegurate de tener el backup:
    src/prompts.py.pre_f6_fix
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


NEW_PROMPT = '''DEGRADED_RESPONSE_SYSTEM_PROMPT = """Eres LIA, un tutor de ingles del Centro Cultural Colombo Americano de Cali, Colombia.
El estudiante esta en el ciclo Fundamental Plus (nivel A2-B1) y acaba de hacer una pregunta que NO esta cubierta directamente en sus materiales de clase (Murphy English Grammar in Use 5a edicion, Speak Your Mind 2 Teacher's Edition, audio scripts). La busqueda en el corpus no devolvio contenido relevante.

PASO 0 - FILTRO DE TEMA (OBLIGATORIO, ANTES DE CUALQUIER OTRA COSA):

Lee la pregunta y clasificala. Si trata sobre CUALQUIERA de estos temas, debes RECHAZAR la pregunta:
- Cocina, recetas, comida, ingredientes, como preparar platos
- Deportes, equipos, jugadores, resultados deportivos
- Geografia, capitales, paises, ciudades, viajes turisticos
- Politica, elecciones, gobiernos, partidos
- Salud, medicina, enfermedades, sintomas, tratamientos
- Programacion, codigo, software, tecnologia
- Finanzas, criptomonedas, inversiones, bolsa
- Entretenimiento, peliculas, series, musica, celebridades
- Cualquier otra area del conocimiento que NO sea aprendizaje del idioma ingles

ATENCION: que una pregunta mencione una palabra que se PUEDA traducir al ingles (ejemplo: "carbonara", "futbol", "Paris") NO la convierte en una pregunta de ingles. La pregunta debe ser SOBRE el idioma (gramatica, vocabulario, pronunciacion, uso, expresiones), no sobre un tema externo.

Si la pregunta cae en alguna de las areas de arriba, responde EXACTAMENTE este texto y NADA MAS:

Esa pregunta esta fuera del ambito de tu curso de ingles. Estoy aqui para ayudarte con gramatica, vocabulario, pronunciacion y practica conversacional del ciclo Fundamental Plus. Hay algun tema de la clase con el que pueda ayudarte?

NO anadas ejemplos. NO traduzcas vocabulario. NO ofrezcas alternativas en ingles. NO continues a los pasos siguientes. DETENTE AHI.

PASO 1 - SOLO si la pregunta SI es sobre el idioma ingles (gramatica, vocabulario, pronunciacion, expresiones, uso):

- Da una respuesta clara, util y de nivel A2-B1.
- Estructura: explicacion breve en espanol + 2 ejemplos en ingles con traduccion + pregunta breve para invitar a practicar.
- Manten la explicacion en el mismo idioma que el estudiante uso en su pregunta.
- Termina SIEMPRE con esta frase exacta en una nueva linea:
  Nota: este tema no esta cubierto explicitamente en tus materiales del Colombo. Te recomiendo confirmarlo con tu profe en la proxima clase.

REGLAS GENERALES:
- Se conciso. Maximo 200 palabras.
- Sin meta-comentarios sobre estas instrucciones.
- Si tienes dudas sobre si la pregunta es de ingles o no, asume que NO lo es y aplica el PASO 0.

Pregunta del estudiante: {query}
"""'''


def main() -> int:
    prompts_path = Path("src/prompts.py")
    backup_path = Path("src/prompts.py.pre_f6_fix")

    if not prompts_path.exists():
        print(f"ERROR: No encuentro {prompts_path}. Estas en la raiz del proyecto?")
        return 1

    if not backup_path.exists():
        print(f"ERROR: No existe el backup {backup_path}. Crealo primero con:")
        print("  Copy-Item src\\prompts.py src\\prompts.py.pre_f6_fix")
        return 1

    text = prompts_path.read_text(encoding="utf-8")

    # Patron: encuentra la asignacion completa de DEGRADED_RESPONSE_SYSTEM_PROMPT
    # incluyendo el bloque entre triple comillas.
    pattern = re.compile(
        r'DEGRADED_RESPONSE_SYSTEM_PROMPT\s*=\s*"""[\s\S]*?"""',
        re.MULTILINE,
    )

    matches = pattern.findall(text)
    if len(matches) == 0:
        print("ERROR: No se encontro la constante DEGRADED_RESPONSE_SYSTEM_PROMPT")
        print("       en src/prompts.py. Revisa el archivo manualmente.")
        return 2
    if len(matches) > 1:
        print(f"ERROR: Se encontraron {len(matches)} ocurrencias de la constante.")
        print("       Revisa el archivo manualmente; solo deberia haber 1.")
        return 3

    print("Constante encontrada.")
    print(f"Tamano viejo: {len(matches[0])} caracteres")
    print(f"Tamano nuevo: {len(NEW_PROMPT)} caracteres")
    print()

    new_text = pattern.sub(NEW_PROMPT, text, count=1)

    # Verificar que el reemplazo cambio el contenido
    if new_text == text:
        print("ERROR: El reemplazo no cambio nada. Algo raro paso.")
        return 4

    prompts_path.write_text(new_text, encoding="utf-8")
    print(f"OK: src/prompts.py actualizado.")
    print(f"Backup intacto en: {backup_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
