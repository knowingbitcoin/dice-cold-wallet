"""Utilidades de dibujo para la pantalla de 240x240: colores, fuentes, dados y QR.

Aquí no hay nada secreto: solo se dibuja lo que la máquina de estados pide.
No se guarda en caché ninguna imagen (solo las fuentes, que son públicas).
"""

from __future__ import annotations

import functools
import pathlib

import qrcode
import qrcode.constants
from PIL import Image, ImageDraw, ImageFont

WIDTH = 240
HEIGHT = 240

# Paleta de alto contraste sobre fondo oscuro.
BG = (8, 11, 16)
PANEL = (28, 34, 44)
TEXT = (245, 245, 245)
MUTED = (165, 175, 186)
ACCENT = (255, 210, 63)  # amarillo: cursor y opción elegida
ACCENT_TEXT = (10, 10, 10)
DANGER = (255, 99, 99)
OK = (110, 220, 140)
DIE_FACE = (236, 236, 232)
DIE_PIP = (15, 15, 20)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Fuente: primero la DejaVu que va con el proyecto, después la del sistema
# (Raspberry Pi OS la trae en esta ruta) y, si no hay ninguna, la de PIL.
_FONT_CANDIDATES = (
    pathlib.Path(__file__).resolve().parent / "fonts" / "DejaVuSans.ttf",
    pathlib.Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)


@functools.lru_cache(maxsize=None)
def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Fuente legible del tamaño pedido (en píxeles)."""
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default(size=size)


def text_width(text: str, size: int) -> float:
    return font(size).getlength(text)


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    size: int,
    fill=TEXT,
    bold: bool = False,
    anchor: str = "la",
) -> None:
    """Escribe texto.

    Con bold=True se engrosa el trazo, porque la fuente solo tiene un peso. Por
    debajo de 20 píxeles el trazo extra emborrona las letras y no se aplica.
    """
    draw.text(
        xy,
        text,
        font=font(size),
        fill=fill,
        anchor=anchor,
        stroke_width=1 if bold and size >= 20 else 0,
        stroke_fill=fill,
    )


def wrap(text: str, size: int, max_width: float) -> list[str]:
    """Parte un texto en líneas que caben en max_width píxeles."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if not current or text_width(candidate, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def fit_size(text: str, size: int, max_width: float, minimum: int = 13) -> int:
    """Tamaño más grande (hasta size) con el que el texto cabe en max_width."""
    while size > minimum and text_width(text, size) > max_width:
        size -= 1
    return size


def draw_paragraph(
    draw: ImageDraw.ImageDraw,
    y: float,
    text: str,
    size: int,
    fill=TEXT,
    bold: bool = False,
    margin: int = 12,
    line_gap: int = 4,
    center: bool = False,
) -> float:
    """Escribe un párrafo con saltos automáticos. Devuelve la y siguiente."""
    for line in wrap(text, size, WIDTH - 2 * margin):
        if center:
            draw_text(draw, (WIDTH / 2, y), line, size, fill, bold, anchor="ma")
        else:
            draw_text(draw, (margin, y), line, size, fill, bold)
        y += size + line_gap
    return y


def draw_help(draw: ImageDraw.ImageDraw, text: str) -> None:
    """Línea de ayuda con los botones, siempre abajo del todo."""
    draw.rectangle((0, HEIGHT - 22, WIDTH, HEIGHT), fill=PANEL)
    size = 14
    while size > 11 and text_width(text, size) > WIDTH - 8:
        size -= 1
    draw_text(draw, (WIDTH / 2, HEIGHT - 11), text, size, MUTED, anchor="mm")


def draw_option(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    label: str,
    selected: bool,
    size: int = 18,
) -> None:
    """Botón de opción: relleno amarillo si está elegido."""
    if selected:
        draw.rounded_rectangle(box, radius=8, fill=ACCENT)
        color = ACCENT_TEXT
    else:
        draw.rounded_rectangle(box, radius=8, outline=MUTED, width=2)
        color = TEXT
    cx = (box[0] + box[2]) / 2
    cy = (box[1] + box[3]) / 2
    draw_text(draw, (cx, cy), label, size, color, bold=selected, anchor="mm")


# Posición de los puntos de cada cara, en una rejilla de 3x3 (columna, fila).
_PIPS = {
    1: [(1, 1)],
    2: [(0, 0), (2, 2)],
    3: [(0, 0), (1, 1), (2, 2)],
    4: [(0, 0), (2, 0), (0, 2), (2, 2)],
    5: [(0, 0), (2, 0), (1, 1), (0, 2), (2, 2)],
    6: [(0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)],
}


def draw_die(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    size: int,
    face: int,
    selected: bool = False,
) -> None:
    """Dibuja una cara del dado con sus puntos."""
    if selected:
        draw.rounded_rectangle(
            (x - 5, y - 5, x + size + 5, y + size + 5), radius=12, fill=ACCENT
        )
    draw.rounded_rectangle((x, y, x + size, y + size), radius=9, fill=DIE_FACE)
    step = size / 4
    radius = size * 0.09
    for col, row in _PIPS[face]:
        cx = x + step * (col + 1)
        cy = y + step * (row + 1)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=DIE_PIP)


# --- QR -----------------------------------------------------------------

QR_BORDER = 4  # módulos de borde blanco (zona de silencio que pide el estándar)

_EC_LEVELS = {
    "M": qrcode.constants.ERROR_CORRECT_M,
    "L": qrcode.constants.ERROR_CORRECT_L,
}


def qr_matrix(payload: str, level: str) -> list[list[bool]]:
    """Matriz de módulos del QR (sin borde) con la versión mínima que cabe."""
    qr = qrcode.QRCode(
        version=None, error_correction=_EC_LEVELS[level], box_size=1, border=0
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.get_matrix()


def fit_qr(payload: str, max_w: int, max_h: int) -> tuple[list[list[bool]], str, int]:
    """Elige el nivel de corrección (M o L) que deja los módulos más grandes.

    Devuelve (matriz, nivel, píxeles por módulo). Si empatan, gana M porque
    aguanta mejor reflejos y suciedad en la pantalla.
    """
    best = None
    for level in ("M", "L"):
        matrix = qr_matrix(payload, level)
        total = len(matrix) + 2 * QR_BORDER
        px = min(max_w, max_h) // total
        if best is None or px > best[2]:
            best = (matrix, level, px)
    matrix, level, px = best
    if px < 1:
        raise ValueError("El código QR no cabe en la pantalla.")
    return matrix, level, px


def draw_qr(
    image: Image.Image, matrix: list[list[bool]], x0: int, y0: int, px: int
) -> int:
    """Pinta el QR con su borde blanco de 4 módulos. Devuelve el lado en píxeles."""
    draw = ImageDraw.Draw(image)
    side = (len(matrix) + 2 * QR_BORDER) * px
    draw.rectangle((x0, y0, x0 + side - 1, y0 + side - 1), fill=WHITE)
    origin_x = x0 + QR_BORDER * px
    origin_y = y0 + QR_BORDER * px
    for row_index, row in enumerate(matrix):
        for col_index, dark in enumerate(row):
            if dark:
                left = origin_x + col_index * px
                top = origin_y + row_index * px
                draw.rectangle((left, top, left + px - 1, top + px - 1), fill=BLACK)
    return side


def blocks_of_four(text: str) -> list[str]:
    """Parte un texto en bloques de 4 caracteres para compararlo a ojo."""
    return [text[i : i + 4] for i in range(0, len(text), 4)]
