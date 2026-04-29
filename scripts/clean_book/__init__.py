"""
clean_book — Pipeline de limpieza de libros pedagógicos del Centro Colombo Americano
para alimentar el RAG de LIA-Colombo AI.

Convierte un PDF nativo digital del Teacher's Edition en un conjunto de archivos
Markdown estructurados (uno por unidad) listos para ser indexados por
`src/document_loader.py`.

Uso:
    python -m scripts.clean_book.cli --pdf data/raw/speak_your_mind_2_te.pdf \\
        --syllabus data/raw/Syllabus_Guide_-_Scope_and_Sequence.xlsx \\
        --cycle "Fundamental Plus" \\
        --out data/raw/

Ver scripts/clean_book/README.md para detalles.
"""

__version__ = "0.1.0"
