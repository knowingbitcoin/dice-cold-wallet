"""Máquina de estados de la cartera: recibe botones y devuelve la imagen de la pantalla.

No sabe nada del hardware. El simulador (sim.py) y la Raspberry (hw.py) le pasan
eventos con WalletApp.handle() y pintan lo que devuelve WalletApp.render().

Recorrido: bienvenida → tiradas → confirmación → aviso → frase → examen →
examen aprobado → cálculo → QR → comprobación → fin.

Sobre los secretos (tiradas, frase):
- Solo viven en atributos de esta clase, en memoria. Nunca se escriben en
  disco, en registros ni en la consola, y ningún mensaje de error los incluye.
- En cuanto dejan de hacer falta se sueltan: las tiradas al generar la frase,
  y la frase al calcular la clave pública. Las listas se vacían en el sitio y
  se llama a gc.collect().
- Python no permite borrar de verdad la memoria: los textos son inmutables y
  el intérprete puede dejar copias hasta que reutiliza ese espacio. Lo que
  borra la semilla de verdad es quitar la corriente, porque la RAM se pierde
  al apagar. Por eso la Raspberry no debe tener memoria de intercambio (swap)
  en la tarjeta SD: ver hw.py.
"""

from __future__ import annotations

import gc

from PIL import Image, ImageDraw

from coldwallet import core
from coldwallet.ui import drawing as d

# Eventos que entiende la aplicación.
UP = "UP"
DOWN = "DOWN"
LEFT = "LEFT"
RIGHT = "RIGHT"
PRESS = "PRESS"
KEY1 = "KEY1"
KEY2 = "KEY2"
KEY3 = "KEY3"
EVENTS = (UP, DOWN, LEFT, RIGHT, PRESS, KEY1, KEY2, KEY3)

# Pantallas.
WELCOME = "bienvenida"
ROLLS = "tiradas"
ROLLS_CONFIRM = "confirmar_tiradas"
WARNING = "aviso"
PHRASE = "frase"
EXAM = "examen"
EXAM_FAIL = "examen_fallado"
EXAM_PASSED = "examen_aprobado"
DERIVING = "calculando"
QR = "qr"
CHECK = "comprobacion"
END = "fin"

WORDS_PER_PAGE = 4
EXAM_QUESTIONS = 3
RECENT_ROLLS = 8

# Rejilla de dados: 3 columnas y 2 filas.
DIE_GRID = ((1, 2, 3), (4, 5, 6))


def face_position(face: int) -> tuple[int, int]:
    """(fila, columna) de una cara en la rejilla."""
    return (face - 1) // 3, (face - 1) % 3


def moves_to_face(current: int, target: int) -> list[str]:
    """Movimientos del joystick para ir de una cara a otra (para pruebas y capturas)."""
    row, col = face_position(current)
    target_row, target_col = face_position(target)
    moves = [DOWN if target_row > row else UP] * abs(target_row - row)
    moves += [RIGHT if target_col > col else LEFT] * abs(target_col - col)
    return moves


def _wipe(items: list | None) -> None:
    """Suelta las referencias de una lista con datos secretos."""
    if items is None:
        return
    for index in range(len(items)):
        items[index] = None
    items.clear()


class WalletApp:
    """Estado completo de la cartera. Se crea vacío y se vacía con KEY2."""

    def __init__(self) -> None:
        self._reset_state()

    # --- estado ---------------------------------------------------------

    def _reset_state(self) -> None:
        self.screen = WELCOME
        self.words = 24
        self._confirm_reset = False
        self._reset_choice = 0  # 0 = no, 1 = sí
        self._cursor = 1  # cara del dado bajo el cursor
        self._rolls: list[str] = []
        self._confirm_choice = 1  # 0 = sí, 1 = volver (por defecto, lo seguro)
        self._mnemonic: list[str] | None = None
        self._page = 0
        self._exam_positions: list[int] = []
        self._exam_index = 0
        self._exam_options: list[str] = []
        self._exam_choice = 0
        self._failed_position = 0
        self._pending = False
        self.account: core.AccountInfo | None = None
        self._first_address = ""
        self.qr_mode = "zpub"
        self.qr_geometry: dict | None = None

    def _wipe_secrets(self) -> None:
        _wipe(self._rolls)
        _wipe(self._mnemonic)
        _wipe(self._exam_options)
        _wipe(self._exam_positions)
        self._mnemonic = None
        gc.collect()

    def reset(self) -> None:
        """Vuelve al principio y suelta todo lo secreto."""
        self._wipe_secrets()
        self._reset_state()

    # --- datos públicos para el simulador, las capturas y las pruebas ---

    @property
    def total_rolls(self) -> int:
        return core.ROLLS_FOR_WORDS[self.words]

    @property
    def rolls_count(self) -> int:
        return len(self._rolls)

    @property
    def cursor_face(self) -> int:
        return self._cursor

    @property
    def confirm_reset_open(self) -> bool:
        return self._confirm_reset

    @property
    def has_phrase(self) -> bool:
        return bool(self._mnemonic)

    @property
    def exam_position(self) -> int:
        """Número de la palabra que se pregunta ahora (desde 1)."""
        return self._exam_positions[self._exam_index] if self.screen == EXAM else 0

    @property
    def exam_options(self) -> list[str]:
        return list(self._exam_options) if self.screen == EXAM else []

    @property
    def exam_choice(self) -> int:
        return self._exam_choice

    @property
    def phrase_page(self) -> int:
        return self._page

    @property
    def has_pending_work(self) -> bool:
        return self._pending

    @property
    def qr_payload(self) -> str:
        """Texto exacto que lleva el QR (público: no permite gastar)."""
        if self.account is None:
            return ""
        return self.account.zpub if self.qr_mode == "zpub" else self.account.descriptor

    # --- eventos --------------------------------------------------------

    def handle(self, event: str) -> None:
        if event not in EVENTS:
            raise ValueError("Botón desconocido.")
        if self._pending:
            return  # mientras calcula no se atiende nada
        if self._confirm_reset:
            self._handle_reset_dialog(event)
            return
        if event == KEY2:
            self._confirm_reset = True
            self._reset_choice = 0
            return
        handler = getattr(self, f"_on_{self.screen}")
        handler(event)

    def _handle_reset_dialog(self, event: str) -> None:
        if event in (UP, DOWN, LEFT, RIGHT):
            self._reset_choice = 1 - self._reset_choice
        elif event == PRESS:
            if self._reset_choice == 1:
                self.reset()
            else:
                self._confirm_reset = False
        elif event == KEY2:
            self._confirm_reset = False

    def _on_bienvenida(self, event: str) -> None:
        if event in (UP, DOWN, LEFT, RIGHT):
            self.words = 12 if self.words == 24 else 24
        elif event == PRESS:
            self._rolls = []
            self._cursor = 1
            self.screen = ROLLS

    def _on_tiradas(self, event: str) -> None:
        row, col = face_position(self._cursor)
        if event == LEFT:
            col = (col - 1) % 3
        elif event == RIGHT:
            col = (col + 1) % 3
        elif event in (UP, DOWN):
            row = 1 - row
        elif event == PRESS:
            if len(self._rolls) < self.total_rolls:
                self._rolls.append(str(self._cursor))
            if len(self._rolls) == self.total_rolls:
                self._confirm_choice = 1
                self.screen = ROLLS_CONFIRM
            return
        elif event == KEY3:
            if self._rolls:
                self._rolls.pop()
            return
        else:
            return
        self._cursor = DIE_GRID[row][col]

    def _on_confirmar_tiradas(self, event: str) -> None:
        if event in (UP, DOWN, LEFT, RIGHT):
            self._confirm_choice = 1 - self._confirm_choice
        elif event == KEY3:
            self._rolls.pop()
            self.screen = ROLLS
        elif event == PRESS:
            if self._confirm_choice == 1:
                self.screen = ROLLS
                return
            rolls = "".join(self._rolls)
            self._mnemonic = core.mnemonic_from_rolls(rolls, self.words)
            del rolls
            _wipe(self._rolls)
            gc.collect()
            self._page = 0
            self.screen = WARNING

    def _on_aviso(self, event: str) -> None:
        if event in (PRESS, RIGHT):
            self._page = 0
            self.screen = PHRASE

    def _pages(self) -> int:
        return len(self._mnemonic) // WORDS_PER_PAGE

    def _on_frase(self, event: str) -> None:
        if event in (PRESS, RIGHT):
            if self._page < self._pages() - 1:
                self._page += 1
            else:
                self._start_exam()
        elif event == LEFT and self._page > 0:
            self._page -= 1

    def _start_exam(self) -> None:
        self._exam_positions = core.quiz_positions(len(self._mnemonic), EXAM_QUESTIONS)
        self._exam_index = 0
        self._new_question()
        self.screen = EXAM

    def _new_question(self) -> None:
        position = self._exam_positions[self._exam_index]
        self._exam_options = core.quiz_options(self._mnemonic, position)
        self._exam_choice = 0

    def _on_examen(self, event: str) -> None:
        count = len(self._exam_options)
        if event in (UP, LEFT):
            self._exam_choice = (self._exam_choice - 1) % count
        elif event in (DOWN, RIGHT):
            self._exam_choice = (self._exam_choice + 1) % count
        elif event == PRESS:
            position = self._exam_positions[self._exam_index]
            right = self._exam_options[self._exam_choice] == self._mnemonic[position - 1]
            _wipe(self._exam_options)
            if not right:
                self._failed_position = position
                _wipe(self._exam_positions)
                self.screen = EXAM_FAIL
                return
            self._exam_index += 1
            if self._exam_index == len(self._exam_positions):
                _wipe(self._exam_positions)
                self.screen = EXAM_PASSED
            else:
                self._new_question()

    def _on_examen_fallado(self, event: str) -> None:
        if event == PRESS:
            self._page = (self._failed_position - 1) // WORDS_PER_PAGE
            self.screen = PHRASE

    def _on_examen_aprobado(self, event: str) -> None:
        if event == PRESS:
            self.screen = DERIVING
            self._pending = True

    def run_pending_work(self) -> None:
        """Cálculo lento (clave pública). Los controladores lo llaman tras pintar."""
        if not self._pending:
            return
        self.account = core.derive_account(self._mnemonic)
        self._first_address = core.receive_addresses(self.account, count=1)[0]
        _wipe(self._mnemonic)
        self._mnemonic = None
        gc.collect()
        self.qr_mode = "zpub"
        self._pending = False
        self.screen = QR

    def _on_calculando(self, event: str) -> None:
        pass

    def _on_qr(self, event: str) -> None:
        if event == KEY1:
            self.qr_mode = "descriptor" if self.qr_mode == "zpub" else "zpub"
        elif event in (PRESS, RIGHT):
            self.screen = CHECK

    def _on_comprobacion(self, event: str) -> None:
        if event in (PRESS, RIGHT):
            self.screen = END
        elif event == LEFT:
            self.screen = QR

    def _on_fin(self, event: str) -> None:
        if event == LEFT:
            self.screen = CHECK

    # --- dibujo ---------------------------------------------------------

    def render(self) -> Image.Image:
        """Imagen nueva de 240x240 con la pantalla actual. No se guarda en ningún sitio."""
        image = Image.new("RGB", (d.WIDTH, d.HEIGHT), d.BG)
        draw = ImageDraw.Draw(image)
        getattr(self, f"_draw_{self.screen}")(image, draw)
        if self._confirm_reset:
            self._draw_reset_dialog(draw)
        return image

    @staticmethod
    def render_error() -> Image.Image:
        """Pantalla de error sin ningún detalle (los detalles podrían ser secretos)."""
        image = Image.new("RGB", (d.WIDTH, d.HEIGHT), d.BG)
        draw = ImageDraw.Draw(image)
        y = d.draw_paragraph(draw, 50, "Algo ha fallado", 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14, "Apaga el aparato y vuelve a empezar.", 18, center=True
        )
        return image

    def _draw_reset_dialog(self, draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle((0, 0, d.WIDTH, d.HEIGHT), fill=d.BG)
        draw.rounded_rectangle((8, 16, 232, 208), radius=12, fill=d.PANEL)
        title = "¿Empezar de nuevo?"
        d.draw_text(draw, (d.WIDTH / 2, 30), title, d.fit_size(title, 22, 200), bold=True, anchor="ma")
        d.draw_paragraph(
            draw, 70, "Se borra todo lo que has hecho.", 17, d.MUTED, center=True,
            margin=24,
        )
        d.draw_option(draw, (20, 146, 114, 190), "No", self._reset_choice == 0, 20)
        d.draw_option(draw, (126, 146, 220, 190), "Sí, borrar", self._reset_choice == 1, 17)
        d.draw_help(draw, "◀ ▶ elegir · Pulsa: aceptar")

    def _draw_bienvenida(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 12), "Cartera fría", 30, d.ACCENT, bold=True, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 56), "Sin red.", 18, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 78), "No guarda nada.", 18, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 110), "¿Cuántas palabras?", 17, d.MUTED, anchor="ma")
        d.draw_option(draw, (16, 136, 114, 180), "12", self.words == 12, 26)
        d.draw_option(draw, (126, 136, 224, 180), "24", self.words == 24, 26)
        d.draw_text(
            draw, (d.WIDTH / 2, 192), "KEY2: empezar de nuevo", 14, d.MUTED, anchor="ma"
        )
        d.draw_help(draw, "◀ ▶ elegir · Pulsa: empezar")

    def _draw_tiradas(self, image, draw) -> None:
        count = len(self._rolls)
        total = self.total_rolls
        # Contador grande.
        d.draw_text(draw, (12, 6), str(count), 36, d.ACCENT, bold=True)
        number_width = d.text_width(str(count), 36) + 2
        d.draw_text(draw, (12 + number_width + 8, 20), f"de {total}", 22, d.TEXT)
        d.draw_text(draw, (228, 12), "Tiradas", 16, d.MUTED, anchor="ra")
        # Barra de progreso.
        draw.rectangle((12, 50, 228, 54), fill=d.PANEL)
        draw.rectangle((12, 50, 12 + int(216 * count / total), 54), fill=d.ACCENT)
        # Últimas tiradas, la más reciente a la derecha.
        recent = self._rolls[-RECENT_ROLLS:]
        box, gap = 24, 3
        x0 = (d.WIDTH - (RECENT_ROLLS * (box + gap) - gap)) // 2
        for slot in range(RECENT_ROLLS):
            index = slot - (RECENT_ROLLS - len(recent))
            x = x0 + slot * (box + gap)
            rect = (x, 62, x + box, 62 + box)
            if index < 0:
                draw.rounded_rectangle(rect, radius=5, outline=d.PANEL, width=2)
                continue
            newest = index == len(recent) - 1
            draw.rounded_rectangle(rect, radius=5, fill=d.TEXT if newest else d.PANEL)
            d.draw_text(
                draw, (x + box / 2, 62 + box / 2), recent[index], 17,
                d.ACCENT_TEXT if newest else d.TEXT, bold=newest, anchor="mm",
            )
        # Rejilla de dados.
        size, gap_x, gap_y = 50, 24, 14
        left = (d.WIDTH - (3 * size + 2 * gap_x)) // 2
        top = 100
        for r, row in enumerate(DIE_GRID):
            for c, face in enumerate(row):
                d.draw_die(
                    draw, left + c * (size + gap_x), top + r * (size + gap_y), size,
                    face, selected=face == self._cursor,
                )
        if count == total:
            d.draw_help(draw, "Pulsa: revisar · KEY3: borrar")
        else:
            d.draw_help(draw, "Pulsa: añadir · KEY3: borrar")

    def _draw_confirmar_tiradas(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 6), "¿Has introducido todas bien?", 15, d.ACCENT, anchor="ma")
        # Todas las tiradas, de 15 en 15, para compararlas con el papel.
        per_row, size, line = 15, 14, 17
        top = 30
        rows = (len(self._rolls) + per_row - 1) // per_row
        digit_w = d.text_width("0", size)
        group_gap = 7
        x_start = 40
        for r in range(rows):
            y = top + r * line
            d.draw_text(draw, (30, y), str(r * per_row + 1), 12, d.MUTED, anchor="ra")
            for i, roll in enumerate(self._rolls[r * per_row : (r + 1) * per_row]):
                x = x_start + i * (digit_w + 3) + (i // 5) * group_gap
                d.draw_text(draw, (x, y), roll, size)
        options_top = 164
        d.draw_option(draw, (10, options_top, 116, options_top + 44), "Sí, seguir", self._confirm_choice == 0, 17)
        d.draw_option(draw, (124, options_top, 230, options_top + 44), "No, volver", self._confirm_choice == 1, 17)
        d.draw_help(draw, "◀ ▶ elegir · Pulsa: aceptar")

    def _draw_aviso(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 20), "!", 44, d.DANGER, bold=True, anchor="ma")
        y = d.draw_paragraph(draw, 76, "Que nadie vea la pantalla", 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 10,
            f"Ten a mano papel y lápiz. Vas a ver {len(self._mnemonic)} palabras.",
            17, center=True,
        )
        d.draw_help(draw, "Pulsa: ver las palabras")

    def _draw_frase(self, image, draw) -> None:
        total = len(self._mnemonic)
        first = self._page * WORDS_PER_PAGE
        d.draw_text(
            draw, (12, 6), f"Palabras {first + 1} a {first + WORDS_PER_PAGE} de {total}",
            16, d.ACCENT, bold=True,
        )
        d.draw_text(draw, (12, 28), "Copia estas palabras en papel", 14, d.MUTED)
        top, step = 56, 40
        for i in range(WORDS_PER_PAGE):
            number = first + i + 1
            y = top + i * step
            d.draw_text(draw, (54, y + 17), f"{number}", 22, d.MUTED, anchor="rm")
            d.draw_text(draw, (64, y + 17), self._mnemonic[number - 1], 30, d.TEXT, bold=True, anchor="lm")
        if self._page < self._pages() - 1:
            help_text = "◀ atrás · ▶ o Pulsa: siguientes"
        else:
            help_text = "◀ atrás · Pulsa: ir al examen"
        d.draw_help(draw, help_text)

    def _draw_examen(self, image, draw) -> None:
        position = self._exam_positions[self._exam_index]
        d.draw_text(
            draw, (12, 6), f"Examen {self._exam_index + 1} de {len(self._exam_positions)}",
            16, d.ACCENT, bold=True,
        )
        question = f"¿Cuál es la palabra {position}?"
        d.draw_text(draw, (12, 30), question, d.fit_size(question, 20, d.WIDTH - 24), bold=True)
        top, height, gap = 62, 33, 5
        for i, option in enumerate(self._exam_options):
            y = top + i * (height + gap)
            d.draw_option(draw, (12, y, 228, y + height), option, i == self._exam_choice, 22)
        d.draw_help(draw, "▲ ▼ elegir · Pulsa: responder")

    def _draw_examen_fallado(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 40, f"Esa no es la palabra {self._failed_position}", 22, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14,
            "Revisa tu copia en papel y corrígela. Después repites el examen.",
            17, center=True,
        )
        d.draw_help(draw, "Pulsa: volver a las palabras")

    def _draw_examen_aprobado(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 10), "Examen aprobado", 24, d.OK, bold=True, anchor="ma")
        y = d.draw_paragraph(
            draw, 50, "Ya no podrás volver a ver la frase.", 16, center=True,
        )
        y = d.draw_paragraph(
            draw, y + 10, "Verás un QR para BlueWallet, Nunchuk o Sparrow.",
            16, d.MUTED, center=True,
        )
        d.draw_paragraph(
            draw, y + 10, "KEY1 cambia entre zpub y descriptor.", 16, d.MUTED, center=True,
        )
        d.draw_help(draw, "Pulsa: ver el QR")

    def _draw_calculando(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 80, "Calculando la clave pública…", 20, center=True)
        d.draw_paragraph(draw, y + 10, "Espera un momento.", 16, d.MUTED, center=True)

    def _draw_qr(self, image, draw) -> None:
        payload = self.qr_payload
        footer = 28
        matrix, level, px = d.fit_qr(payload, d.WIDTH, d.HEIGHT - footer)
        side = (len(matrix) + 2 * d.QR_BORDER) * px
        x0 = (d.WIDTH - side) // 2
        y0 = max(0, (d.HEIGHT - footer - side) // 2)
        d.draw_qr(image, matrix, x0, y0, px)
        self.qr_geometry = {
            "x0": x0, "y0": y0, "px": px, "modules": len(matrix), "level": level,
        }
        label = "zpub" if self.qr_mode == "zpub" else "Descriptor"
        info = f"{label} · {self.account.fingerprint}"
        text_y = d.HEIGHT - footer / 2
        d.draw_text(draw, (6, text_y), info, 14, d.TEXT, anchor="lm")
        d.draw_text(draw, (d.WIDTH - 6, text_y), "KEY1 ⇄", 14, d.ACCENT, anchor="rm")

    def _draw_comprobacion(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 6), "Compara con tu iPhone", 18, d.ACCENT, bold=True, anchor="ma")
        d.draw_text(draw, (12, 34), "Huella maestra", 15, d.MUTED)
        x = 12
        for block in d.blocks_of_four(self.account.fingerprint):
            d.draw_text(draw, (x, 54), block, 24, bold=True)
            x += 74
        d.draw_text(draw, (12, 92), "Primera dirección de cobro", 15, d.MUTED)
        blocks = d.blocks_of_four(self._first_address)
        col_w, row_h = 56, 28
        for i, block in enumerate(blocks):
            row, col = divmod(i, 4)
            center = 8 + col * col_w + col_w / 2
            d.draw_text(draw, (center, 116 + row * row_h), block, 20, anchor="ma")
        d.draw_help(draw, "◀ volver al QR · Pulsa: terminar")

    def _draw_fin(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 40, "Apaga el aparato", 26, d.ACCENT, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14, "La semilla se borra al quitar la corriente.", 18, center=True,
        )
        d.draw_help(draw, "KEY2: empezar de nuevo")
