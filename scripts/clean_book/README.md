# clean_book — Pipeline de limpieza del Teacher's Edition

Convierte un PDF nativo del **Speak Your Mind 2 Teacher's Edition** en archivos
Markdown estructurados (uno por unidad) listos para ingestión por el RAG de LIA.

Salida diseñada para ser indexada por `src/document_loader.py`: cada `.md`
trae frontmatter YAML con `cycle`, `unit`, `level`, `grammar`, `vocabulary`,
y el contenido está organizado en `## Lesson 1A — ...` / `### Vocabulary` /
`### Grammar` / `### Teacher Notes`.

## Instalación

Dependencias adicionales (no están en el `pyproject.toml` principal porque
solo se usan en este pipeline offline):

```bash
uv pip install pdfplumber pyyaml
```

O añadir a un grupo de dev en `pyproject.toml`:

```toml
[project.optional-dependencies]
clean = ["pdfplumber>=0.11.0", "pyyaml>=6.0.1"]
```

Luego: `uv sync --extra clean`.

## Workflow recomendado

### Paso 1 — Auditoría (siempre primero)

Corre con `--audit-only` para inspeccionar el PDF y obtener sugerencias de
heurísticas (font sizes, boilerplate, candidatos a Unit headers):

```bash
python -m scripts.clean_book.cli \
    --pdf data/raw/speak_your_mind_2_te.pdf \
    --syllabus data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx \
    --out data/clean_book_audit \
    --audit-only -v
```

Esto genera `data/clean_book_audit/audit_report.json` y un resumen humano en stdout.

**Revisa los valores propuestos** y ajusta `configs/speak_your_mind_2.yaml`:
- `unit_boundary.min_font_size`
- `lesson_boundary.min_font_size`
- Si ves boilerplate adicional repetido, agrégalo a `noise.drop_line_patterns`
- Si los "candidatos a Unit" no aciertan, ajusta los regex en `unit_boundary.patterns`

### Paso 2 — Prueba sobre un rango pequeño

Antes de procesar todo el libro, corre sobre las primeras N páginas (típicamente
las que cubren Unit 1) en modo permisivo:

```bash
python -m scripts.clean_book.cli \
    --pdf data/raw/speak_your_mind_2_te.pdf \
    --syllabus data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx \
    --out data/clean_book_test \
    --pages 1-30 \
    --permissive -v
```

Inspecciona el `.md` resultante. Verifica:
- ¿El header `# Unit 1 — Extraordinary` está bien?
- ¿Las lessons (`## Lesson 1A`, etc.) se detectaron?
- ¿Las teacher notes están separadas en `### Teacher Notes`?
- ¿No hay basura de boilerplate en el cuerpo?
- ¿Las tablas de gramática se preservaron como Markdown tables?

Si no, vuelve al Paso 1 y ajusta el YAML.

### Paso 3 — Pipeline completo en modo estricto

Cuando estés satisfecho con la calidad del Paso 2, corre sobre todo el libro:

```bash
python -m scripts.clean_book.cli \
    --pdf data/raw/speak_your_mind_2_te.pdf \
    --syllabus data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx \
    --cycle "Fundamental Plus" \
    --out data/raw \
    --strict -v
```

Si la validación falla (modo estricto), corregir el YAML o usar `--permissive`
y luego revisar los TODOs marcados en los `.md`.

### Paso 4 — Re-indexación del RAG

Los archivos generados están en `data/raw/`, donde `document_loader.py`
los recoge automáticamente. Iniciar la app, login admin, "Re-indexar".

## Para Fundamental (futura extensión)

```bash
python -m scripts.clean_book.cli \
    --pdf data/raw/speak_your_mind_1_te.pdf \
    --syllabus data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx \
    --cycle "Fundamental" \
    --out data/raw
```

Si el libro de Fundamental usa heurísticas distintas (font sizes, layout),
crear un `configs/speak_your_mind_1.yaml` y pasarlo con `--config`.

## Estructura de salida

Para Fundamental Plus, esperar 12 archivos:

```
data/raw/
├── fundamental_plus_unit01_extraordinary.md
├── fundamental_plus_unit02_party.md
├── fundamental_plus_unit03_whats_trending.md
├── ...
└── fundamental_plus_unit12_im_a_member.md
```

Cada archivo tiene la forma:

```markdown
---
cycle: Fundamental Plus
unit: 1
unit_name: Extraordinary
grammar:
  - Past Progressive
  - Past Progressive vs. Simple Past
vocabulary:
  - Role Models
  - Reactions
  - Family Situations
source_pdf: speak_your_mind_2_te.pdf
source_type: book
---

# Unit 1 — Extraordinary

## Introducción de la unidad
...

## Lesson 1A — Heroes

### Vocabulary
...

### Grammar
...

### Teacher Notes
...
```

## Troubleshooting

### "No se detectaron unidades en el PDF"

Causas comunes:
1. El font size mínimo de Unit en el YAML es demasiado alto o bajo.
2. El PDF tiene OCR (no es nativo digital). Verificar con
   `pdftotext -layout pdf.pdf - | head -30`.
3. Los headers usan tipografía no estándar. Correr con `-vv` para ver los
   bloques candidatos descartados.

### "Validación falló — Unit X missing"

El detector no encontró esa unidad. Posibles fixes:
- Bajar `unit_boundary.min_font_size` en el YAML.
- Agregar un patrón regex adicional en `unit_boundary.patterns`.
- Si la unidad se llama distinto en el PDF que en el syllabus, corregir el
  syllabus o el PDF.

### "Grammar mismatch"

El validador esperaba encontrar términos como "past progressive" en la
Unit 1, pero no los halló. Posibles causas:
- La detección de fronteras de Unit es incorrecta (Unit 1 incluye contenido
  que no le corresponde).
- El libro usa terminología distinta (ej. "Continuous Past" en vez de
  "Past Progressive").

Acción: revisar manualmente la unidad afectada. Si la terminología es
distinta pero pedagógicamente equivalente, anotarlo en el TODO del .md.

### Las teacher_notes no se separan correctamente

Ajustar en el YAML:
- `teacher_notes.text_markers`: agregar marcadores adicionales que veas en el PDF.
- `teacher_notes.sidebar_width_ratio_max`: si las notas son más anchas, subir.
- Considerar agregar `use_background_color: true` (requiere extender el
  extractor para leer fill colors — pendiente).

## Diseño y limitaciones conocidas

- **No procesa imágenes**. El Teacher's Edition tiene fotos e ilustraciones;
  estas se omiten porque BGE-M3 es text-only.
- **No resuelve referencias cruzadas**. "Use the example on page 14" se deja
  literal; el RAG en runtime lo manejará si el chunk lo necesita.
- **Heurísticas, no LLM**. El proceso es 100% determinista (no hay llamadas
  a LLM). Esto es deliberado: reproducible, gratuito, rápido. La contrapartida
  es que ediciones con layout muy distinto pueden requerir un YAML específico.
- **Tablas pueden fallar**. Si pdfplumber no encuentra líneas, las tablas se
  pierden. Para libros con tablas borderless, considerar `vertical_strategy:
  text` en el YAML.

## Tests

```bash
python -m pytest scripts/clean_book/tests/
```
