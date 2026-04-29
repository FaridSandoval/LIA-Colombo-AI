"""
Extracción cruda del PDF con pdfplumber.

Estrategia clave: NO detectar columnas a nivel de página entera (eso falla
con layouts mixtos). En su lugar:
1. Filtrar chars decorativos (size < MIN_READABLE_SIZE).
2. Dividir cada página en BANDAS Y (separadas por gaps verticales grandes).
3. Para cada banda, detectar sus columnas localmente analizando los clusters
   horizontales por línea.
4. Concatenar bloques en orden: banda 1 (col 1, col 2, ...) → banda 2 → ...
"""
from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber

logger = logging.getLogger(__name__)

# Umbrales y constantes
BIG_FONT_THRESHOLD = 30.0       # Líneas con fuente >= esto = bloque solo
MIN_READABLE_SIZE = 5.5          # Chars con tamaño < esto = decorativos
Y_BAND_GAP = 20.0                # Gap Y > esto = nueva banda vertical
LINE_TOL = 1.5                   # Tolerancia vertical para agrupar chars en una línea
CLUSTER_GAP = 15.0               # Gap horizontal > esto = nuevo cluster en una línea
COLUMN_PROXIMITY = 30.0          # Clusters con x_start < esto px = misma columna


@dataclass
class Block:
    page: int
    text: str
    font_size: float
    font_name: str
    x0: float
    y0: float
    x1: float
    y1: float
    is_bold: bool = False
    is_italic: bool = False
    page_width: float = 0.0
    page_height: float = 0.0

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def width_ratio(self) -> float:
        return self.width / self.page_width if self.page_width > 0 else 0.0


@dataclass
class Table:
    page: int
    cells: list[list[Optional[str]]]
    bbox: tuple[float, float, float, float]


@dataclass
class PageContent:
    blocks: list[Block] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0


def _font_flags(font_name: str) -> tuple[bool, bool]:
    name_lc = (font_name or "").lower()
    is_bold = any(tok in name_lc for tok in ("bold", "black", "heavy", "-bd"))
    is_italic = any(tok in name_lc for tok in ("italic", "oblique", "-it"))
    return is_bold, is_italic


def _detect_y_bands(chars: list[dict]) -> list[list[dict]]:
    """Divide chars en bandas separadas por gap vertical > Y_BAND_GAP."""
    if not chars:
        return []
    by_top: dict[int, list[dict]] = defaultdict(list)
    for c in chars:
        by_top[round(c["top"], 0)].append(c)
    sorted_tops = sorted(by_top.keys())
    if not sorted_tops:
        return []
    band_tops: list[list[float]] = [[sorted_tops[0]]]
    for top in sorted_tops[1:]:
        if top - band_tops[-1][-1] > Y_BAND_GAP:
            band_tops.append([top])
        else:
            band_tops[-1].append(top)
    bands: list[list[dict]] = []
    for tops in band_tops:
        cs: list[dict] = []
        for top in tops:
            cs.extend(by_top[top])
        bands.append(cs)
    return bands


def _cluster_line(chars: list[dict]) -> list[list[dict]]:
    """Agrupa chars de una línea en clusters separados por gap > CLUSTER_GAP."""
    if not chars:
        return []
    chars_sorted = sorted(chars, key=lambda c: c["x0"])
    clusters: list[list[dict]] = [[chars_sorted[0]]]
    for c in chars_sorted[1:]:
        gap = c["x0"] - clusters[-1][-1]["x1"]
        if gap > CLUSTER_GAP:
            clusters.append([c])
        else:
            clusters[-1].append(c)
    return clusters


def _build_block_from_chars(chars: list[dict], page_num: int,
                            page_w: float, page_h: float) -> Optional[Block]:
    """Construye un Block a partir de una lista de chars."""
    if not chars:
        return None
    text = "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"]))
    if not text.strip():
        return None
    sizes = [c["size"] for c in chars]
    fonts = [c["fontname"] for c in chars]
    font_size = statistics.median(sizes)
    font_name = max(set(fonts), key=fonts.count)
    is_bold, is_italic = _font_flags(font_name)
    return Block(
        page=page_num, text=text.strip(),
        font_size=round(font_size, 2),
        font_name=font_name,
        x0=min(c["x0"] for c in chars),
        x1=max(c["x1"] for c in chars),
        y0=min(c["top"] for c in chars),
        y1=max(c["bottom"] for c in chars),
        is_bold=is_bold, is_italic=is_italic,
        page_width=page_w, page_height=page_h,
    )


def _process_band(band_chars: list[dict], page_num: int,
                  page_w: float, page_h: float) -> list[Block]:
    """
    Procesa una banda Y:
    1. Para cada línea, detecta sus clusters.
    2. Agrupa los clusters de todas las líneas en "columnas virtuales"
       según x_start cercano.
    3. Cada columna virtual produce bloques en orden vertical.
    """
    # Agrupar por línea
    by_top: dict[int, list[dict]] = defaultdict(list)
    for c in band_chars:
        by_top[round(c["top"], 0)].append(c)
    if not by_top:
        return []

    # Detectar clusters por línea, separando big-font de cuerpo
    # Cada cluster es: (top, x_start, chars)
    line_clusters: list[tuple[float, float, list[dict]]] = []
    for top in sorted(by_top.keys()):
        chars = by_top[top]
        # Big-font lines: cada char una línea, no se clusteriza
        clusters = _cluster_line(chars)
        for cl in clusters:
            x_start = min(c["x0"] for c in cl)
            line_clusters.append((top, x_start, cl))

    if not line_clusters:
        return []

    # Identificar "columnas virtuales" agrupando clusters por x_start cercano
    # Ordenar todos los x_start únicos y cluster los cercanos
    all_x_starts = sorted({lc[1] for lc in line_clusters})
    column_anchors: list[float] = []  # x_start canónico de cada columna
    for x in all_x_starts:
        if not column_anchors or x - column_anchors[-1] > COLUMN_PROXIMITY:
            column_anchors.append(x)
        # Sino: pertenece a la columna anterior

    if not column_anchors:
        return []

    # Para cada cluster, decidir a qué columna pertenece (el anchor más cercano por debajo)
    def assign_column(x_start: float) -> int:
        col = 0
        for i, anchor in enumerate(column_anchors):
            if x_start >= anchor - COLUMN_PROXIMITY * 0.5:
                col = i
            else:
                break
        return col

    # Agrupar clusters por columna, manteniendo orden por top
    columns_clusters: list[list[tuple[float, list[dict]]]] = [[] for _ in column_anchors]
    for top, x_start, cl in line_clusters:
        col_idx = assign_column(x_start)
        columns_clusters[col_idx].append((top, cl))

    # Para cada columna, construir bloques
    all_blocks: list[Block] = []
    for col_clusters in columns_clusters:
        if not col_clusters:
            continue
        col_clusters.sort(key=lambda p: p[0])

        # Dentro de la columna, separar por big-font (cada línea grande es bloque solo)
        # y agrupar líneas pequeñas consecutivas en bloques
        small_buffer: list[tuple[float, list[dict]]] = []

        def flush_small():
            if not small_buffer:
                return
            # Construir un bloque concatenando líneas con \n
            all_chars: list[dict] = []
            text_lines: list[str] = []
            for top, cl in small_buffer:
                text_lines.append("".join(c["text"] for c in sorted(cl, key=lambda c: c["x0"])))
                all_chars.extend(cl)
            joined_text = "\n".join(t for t in text_lines if t.strip())
            if not joined_text.strip():
                small_buffer.clear()
                return
            sizes = [c["size"] for c in all_chars]
            fonts = [c["fontname"] for c in all_chars]
            font_size = statistics.median(sizes)
            font_name = max(set(fonts), key=fonts.count)
            is_bold, is_italic = _font_flags(font_name)
            blk = Block(
                page=page_num, text=joined_text,
                font_size=round(font_size, 2), font_name=font_name,
                x0=min(c["x0"] for c in all_chars),
                x1=max(c["x1"] for c in all_chars),
                y0=min(c["top"] for c in all_chars),
                y1=max(c["bottom"] for c in all_chars),
                is_bold=is_bold, is_italic=is_italic,
                page_width=page_w, page_height=page_h,
            )
            all_blocks.append(blk)
            small_buffer.clear()

        last_top = None
        last_size = None
        for top, cl in col_clusters:
            sizes = [c["size"] for c in cl]
            line_size = statistics.median(sizes)

            if line_size >= BIG_FONT_THRESHOLD:
                flush_small()
                blk = _build_block_from_chars(cl, page_num, page_w, page_h)
                if blk:
                    all_blocks.append(blk)
                last_top = top
                last_size = line_size
                continue

            # Si hay buffer y la fuente cambió mucho o el gap Y es grande, flush
            if small_buffer and last_size is not None:
                size_changed = abs(line_size - last_size) > 1.0
                gap_y = top - last_top if last_top else 0
                if size_changed or gap_y > 1.5 * line_size:
                    flush_small()

            small_buffer.append((top, cl))
            last_top = top
            last_size = line_size

        flush_small()

    return all_blocks


def _extract_blocks_from_page(page: pdfplumber.page.Page, page_num: int) -> list[Block]:
    """Pipeline completo: filtrar → bandas Y → procesar cada banda."""
    if not page.chars:
        return []
    clean = [c for c in page.chars if c["size"] >= MIN_READABLE_SIZE]
    if not clean:
        return []
    bands = _detect_y_bands(clean)
    all_blocks: list[Block] = []
    for band in bands:
        all_blocks.extend(_process_band(band, page_num, page.width, page.height))
    return all_blocks


def _extract_tables(page: pdfplumber.page.Page, page_num: int,
                    settings: dict) -> list[Table]:
    tables: list[Table] = []
    try:
        found = page.find_tables(table_settings=settings)
    except Exception as e:
        logger.debug("Tabla detection falló en página %d: %s", page_num, e)
        return []
    for t in found:
        cells = t.extract()
        if not cells:
            continue
        bbox = t.bbox
        tables.append(Table(page=page_num, cells=cells, bbox=bbox))
    return tables


def extract_pdf(pdf_path: Path, table_settings: Optional[dict] = None,
                page_range: Optional[tuple[int, int]] = None) -> list[PageContent]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF no encontrado: {pdf_path}")

    table_settings = table_settings or {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
    }

    pages: list[PageContent] = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        start, end = page_range or (1, total)
        end = min(end, total)
        logger.info("Extrayendo páginas %d–%d de %s (%d total)",
                    start, end, pdf_path.name, total)

        for i in range(start - 1, end):
            page = pdf.pages[i]
            blocks = _extract_blocks_from_page(page, page_num=i + 1)
            tables = _extract_tables(page, page_num=i + 1, settings=table_settings)
            pages.append(PageContent(
                blocks=blocks, tables=tables,
                width=page.width, height=page.height,
            ))
    logger.info("Extraídos %d páginas, %d bloques totales.",
                len(pages), sum(len(p.blocks) for p in pages))
    return pages
