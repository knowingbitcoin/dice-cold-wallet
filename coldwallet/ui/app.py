"""Máquina de estados de la cartera: recibe botones y devuelve la imagen de la pantalla.

No sabe nada del hardware. El simulador (sim.py) y la Raspberry (hw.py) le pasan
eventos con WalletApp.handle() y pintan lo que devuelve WalletApp.render().

Recorrido: bienvenida → tiradas → revisión de las tiradas → confirmación →
aviso → frase → examen (todas las palabras) → examen aprobado → cálculo →
QR → comprobación → fin.

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
  en la tarjeta SD: ver el README.
"""

from __future__ import annotations

import gc
import time

from PIL import Image, ImageDraw

from coldwallet import core
from coldwallet.ui import drawing as d
from coldwallet.ui import i18n

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
DIRECTIONS = (UP, DOWN, LEFT, RIGHT)

# Pantallas.
WELCOME = "bienvenida"
ROLLS = "tiradas"
ROLLS_CONFIRM = "revisar_tiradas"
ROLLS_FINAL = "confirmar_tiradas"
ROLLS_BAD = "tiradas_raras"
WARNING = "aviso"
PHRASE = "frase"
EXAM = "examen"
EXAM_FAIL = "examen_fallado"
EXAM_PASSED = "examen_aprobado"
DERIVING = "calculando"
MISMATCH = "no_coincide"
QR = "qr"
CHECK = "comprobacion"
END = "fin"

WORDS_PER_PAGE = 4
RECENT_ROLLS = 8

# Revisión de tiradas: 5 filas de 5 por página, con números grandes.
REVIEW_COLS = 5
REVIEW_ROWS = 5
REVIEW_PER_PAGE = REVIEW_COLS * REVIEW_ROWS

# Modos de la pantalla de la frase.
PHRASE_FIRST = "primera"  # primera vez: se pasa de página y al final va al examen
PHRASE_FIX = "corregir"  # tras un fallo: se corrige y se vuelve a la misma pregunta
PHRASE_REVIEW = "repasar"  # tras aprobar: se repasa y se vuelve a «examen aprobado»

# Rejilla de dados: 3 columnas y 2 filas.
DIE_GRID = ((1, 2, 3), (4, 5, 6))

# Antirrebote humano: una segunda pulsación de estos botones antes de este
# tiempo se descarta (evita sumar dos tiradas, saltarse páginas o responder
# dos preguntas con una sola pulsación). El antirrebote eléctrico de 50 ms
# de hw.py no basta para eso.
REPEAT_GUARD_SECONDS = 0.35
GUARDED_EVENTS = (PRESS, KEY1, KEY3)


class RepeatGuard:
    """Descarta la repetición demasiado rápida de un mismo botón."""

    def __init__(self, interval: float = REPEAT_GUARD_SECONDS, clock=time.monotonic) -> None:
        self._interval = interval
        self._clock = clock
        self._last: dict[str, float] = {}

    def accept(self, event: str) -> bool:
        if event not in GUARDED_EVENTS:
            return True
        now = self._clock()
        last = self._last.get(event)
        if last is not None and now - last < self._interval:
            return False
        self._last[event] = now
        return True


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
    """Estado completo de la cartera. Se crea vacío y se vacía con KEY2.

    lang es el idioma de los textos de la pantalla (en, es o pt). No cambia nada
    más: las palabras de la frase son siempre las BIP39 en inglés y los botones
    hacen lo mismo en todos los idiomas. Empezar de nuevo conserva el idioma.
    """

    def __init__(self, lang: str = i18n.DEFAULT_LANGUAGE) -> None:
        self.lang = i18n.check_language(lang)
        self._reset_state()

    # --- estado ---------------------------------------------------------

    def _reset_state(self) -> None:
        self.screen = WELCOME
        self.words = 24
        self._confirm_reset = False
        self._reset_choice = 0  # 0 = no, 1 = sí
        self._cursor = 1  # cara del dado bajo el cursor
        self._rolls: list[str] = []
        self._review_index = 0  # tirada bajo el cursor en la revisión
        self._editing = False
        self._edit_original = ""
        self._final_choice = 1  # 0 = sí, 1 = revisar (por defecto, lo seguro)
        self._rolls_problem = ""
        self._mnemonic: list[str] | None = None
        self._page = 0
        self._phrase_mode = PHRASE_FIRST
        self._exam_positions: list[int] = []
        self._exam_index = 0
        self._exam_options: list[str] = []
        self._exam_choice = 0
        self._failed_position = 0
        self._passed_choice = 0  # 0 = repasar las palabras (lo seguro), 1 = seguir al QR
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
        self._edit_original = ""
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
    def review_index(self) -> int:
        return self._review_index

    @property
    def editing(self) -> bool:
        return self._editing

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
    def exam_total(self) -> int:
        return len(self._exam_positions)

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
    def phrase_mode(self) -> str:
        return self._phrase_mode

    @property
    def has_pending_work(self) -> bool:
        return self._pending

    @property
    def qr_payload(self) -> str:
        """Texto exacto que lleva el QR (público: no permite gastar)."""
        if self.account is None:
            return ""
        if self.qr_mode == "zpub":
            return self.account.zpub
        return self.account.descriptor_multipath

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
        if event in DIRECTIONS:
            self._reset_choice = 1 - self._reset_choice
        elif event == PRESS:
            if self._reset_choice == 1:
                self.reset()
            else:
                self._confirm_reset = False
        elif event == KEY2:
            self._confirm_reset = False

    def _on_bienvenida(self, event: str) -> None:
        # Solo ◀ ▶ cambian la opción: un toque vertical al pulsar no la cambia.
        if event in (LEFT, RIGHT):
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
                self._open_review()
            return
        elif event == KEY3:
            if self._rolls:
                self._rolls.pop()
            return
        else:
            return
        self._cursor = DIE_GRID[row][col]

    def _open_review(self) -> None:
        self._review_index = 0
        self._editing = False
        self.screen = ROLLS_CONFIRM

    def _on_revisar_tiradas(self, event: str) -> None:
        last = len(self._rolls) - 1
        if self._editing:
            value = int(self._rolls[self._review_index])
            if event in (UP, RIGHT):
                self._rolls[self._review_index] = str(value % 6 + 1)
            elif event in (DOWN, LEFT):
                self._rolls[self._review_index] = str((value - 2) % 6 + 1)
            elif event == PRESS:
                self._editing = False
                self._edit_original = ""
            elif event == KEY3:  # deshacer el cambio
                self._rolls[self._review_index] = self._edit_original
                self._editing = False
                self._edit_original = ""
            return
        if event == LEFT:
            self._review_index = max(0, self._review_index - 1)
        elif event == RIGHT:
            self._review_index = min(last, self._review_index + 1)
        elif event == UP:
            self._review_index = max(0, self._review_index - REVIEW_COLS)
        elif event == DOWN:
            self._review_index = min(last, self._review_index + REVIEW_COLS)
        elif event == PRESS:
            self._editing = True
            self._edit_original = self._rolls[self._review_index]
        elif event == KEY1:
            self._final_choice = 1
            self.screen = ROLLS_FINAL
        elif event == KEY3:
            self._rolls.pop()
            self.screen = ROLLS

    def _on_confirmar_tiradas(self, event: str) -> None:
        if event in DIRECTIONS:
            self._final_choice = 1 - self._final_choice
        elif event == PRESS:
            if self._final_choice == 1:
                self.screen = ROLLS_CONFIRM
                return
            rolls = "".join(self._rolls)
            problem = core.rolls_quality_problem(rolls)
            if problem:
                del rolls
                self._rolls_problem = problem
                self.screen = ROLLS_BAD
                return
            self._mnemonic = core.mnemonic_from_rolls(rolls, self.words)
            same = core.independent_mnemonic_matches(rolls, self.words, self._mnemonic)
            del rolls
            _wipe(self._rolls)
            gc.collect()
            if not same:
                self._fail_mismatch()
                return
            self._page = 0
            self._phrase_mode = PHRASE_FIRST
            self.screen = WARNING

    def _on_tiradas_raras(self, event: str) -> None:
        if event == PRESS:
            self._open_review()

    def _on_aviso(self, event: str) -> None:
        if event in (PRESS, RIGHT):
            self._page = 0
            self.screen = PHRASE

    def _pages(self) -> int:
        return len(self._mnemonic) // WORDS_PER_PAGE

    def _on_frase(self, event: str) -> None:
        last_page = self._pages() - 1
        if self._phrase_mode == PHRASE_FIRST:
            if event in (PRESS, RIGHT):
                if self._page < last_page:
                    self._page += 1
                else:
                    self._start_exam()
            elif event == LEFT and self._page > 0:
                self._page -= 1
            return
        # Corregir o repasar: ◀ ▶ pasan páginas y Pulsa vuelve.
        if event == RIGHT and self._page < last_page:
            self._page += 1
        elif event == LEFT and self._page > 0:
            self._page -= 1
        elif event == PRESS:
            if self._phrase_mode == PHRASE_FIX:
                self._new_question()
                self.screen = EXAM
            else:
                self._passed_choice = 0
                self.screen = EXAM_PASSED

    def _start_exam(self) -> None:
        # Se preguntan TODAS las palabras, en orden, mirando el papel.
        n_words = len(self._mnemonic)
        self._exam_positions = core.quiz_positions(n_words, n_words)
        self._exam_index = 0
        self._new_question()
        self.screen = EXAM

    def _new_question(self) -> None:
        position = self._exam_positions[self._exam_index]
        self._exam_options = core.quiz_options(self._mnemonic, position)
        self._exam_choice = 0

    def _on_examen(self, event: str) -> None:
        count = len(self._exam_options)
        position = self._exam_positions[self._exam_index]
        if event in (UP, LEFT):
            self._exam_choice = (self._exam_choice - 1) % count
        elif event in (DOWN, RIGHT):
            self._exam_choice = (self._exam_choice + 1) % count
        elif event == KEY3:  # «no está en mi papel»
            _wipe(self._exam_options)
            self._failed_position = position
            self.screen = EXAM_FAIL
        elif event == PRESS:
            right = self._exam_options[self._exam_choice] == self._mnemonic[position - 1]
            _wipe(self._exam_options)
            if not right:
                self._failed_position = position
                self.screen = EXAM_FAIL
                return
            self._exam_index += 1
            if self._exam_index == len(self._exam_positions):
                _wipe(self._exam_positions)
                self._exam_index = 0
                self._passed_choice = 0
                self.screen = EXAM_PASSED
            else:
                self._new_question()

    def _on_examen_fallado(self, event: str) -> None:
        if event == PRESS:
            self._page = (self._failed_position - 1) // WORDS_PER_PAGE
            self._phrase_mode = PHRASE_FIX
            self.screen = PHRASE

    def _on_examen_aprobado(self, event: str) -> None:
        if event in DIRECTIONS:
            self._passed_choice = 1 - self._passed_choice
        elif event == PRESS:
            if self._passed_choice == 0:
                self._page = 0
                self._phrase_mode = PHRASE_REVIEW
                self.screen = PHRASE
            else:
                self.screen = DERIVING
                self._pending = True

    def run_pending_work(self) -> None:
        """Cálculo lento (clave pública). Los controladores lo llaman tras pintar.

        La cuenta se calcula dos veces: con embit y con la implementación
        independiente de crosscheck. Si no coinciden, no se enseña ningún QR.
        """
        if not self._pending:
            return
        account = core.derive_account(self._mnemonic)
        first_address = core.receive_addresses(account, count=1)[0]
        same = core.independent_account_matches(self._mnemonic, account, first_address)
        _wipe(self._mnemonic)
        self._mnemonic = None
        gc.collect()
        self._pending = False
        if not same:
            self._fail_mismatch()
            return
        self.account = account
        self._first_address = first_address
        self.qr_mode = "zpub"
        self.screen = QR

    def _fail_mismatch(self) -> None:
        self._wipe_secrets()
        self.account = None
        self._first_address = ""
        self.screen = MISMATCH

    def _on_no_coincide(self, event: str) -> None:
        pass  # solo se sale apagando o con KEY2

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

    def _t(self, key: str, **values) -> str:
        return i18n.t(key, self.lang, **values)

    def render(self) -> Image.Image:
        """Imagen nueva de 240x240 con la pantalla actual. No se guarda en ningún sitio."""
        image = Image.new("RGB", (d.WIDTH, d.HEIGHT), d.BG)
        draw = ImageDraw.Draw(image)
        getattr(self, f"_draw_{self.screen}")(image, draw)
        if self._confirm_reset:
            self._draw_reset_dialog(draw)
        return image

    @staticmethod
    def render_error(lang: str = i18n.DEFAULT_LANGUAGE) -> Image.Image:
        """Pantalla de error sin ningún detalle (los detalles podrían ser secretos)."""
        image = Image.new("RGB", (d.WIDTH, d.HEIGHT), d.BG)
        draw = ImageDraw.Draw(image)
        y = d.draw_paragraph(draw, 50, i18n.t("error.title", lang), 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14, i18n.t("error.body", lang), 18, center=True
        )
        return image

    @staticmethod
    def render_network_warning(lang: str = i18n.DEFAULT_LANGUAGE) -> Image.Image:
        """Pantalla que bloquea la cartera si el sistema tiene una conexión de red."""
        image = Image.new("RGB", (d.WIDTH, d.HEIGHT), d.BG)
        draw = ImageDraw.Draw(image)
        y = d.draw_paragraph(draw, 34, i18n.t("network.title", lang), 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14,
            i18n.t("network.body", lang),
            17, center=True,
        )
        return image

    def _draw_reset_dialog(self, draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle((0, 0, d.WIDTH, d.HEIGHT), fill=d.BG)
        draw.rounded_rectangle((8, 16, 232, 208), radius=12, fill=d.PANEL)
        title = self._t("reset.title")
        d.draw_text(draw, (d.WIDTH / 2, 30), title, d.fit_size(title, 22, 200), bold=True, anchor="ma")
        d.draw_paragraph(
            draw, 70, self._t("reset.body"), 17, d.MUTED, center=True,
            margin=24,
        )
        d.draw_option(draw, (20, 146, 114, 190), self._t("reset.no"), self._reset_choice == 0, 20)
        d.draw_option(draw, (126, 146, 220, 190), self._t("reset.yes"), self._reset_choice == 1, 17)
        d.draw_help(draw, self._t("help.choose_accept"))

    def _draw_bienvenida(self, image, draw) -> None:
        title = self._t("welcome.title")
        d.draw_text(draw, (d.WIDTH / 2, 12), title, d.fit_size(title, 30, d.WIDTH - 16), d.ACCENT, bold=True, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 56), self._t("welcome.offline"), 18, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 78), self._t("welcome.stores_nothing"), 18, anchor="ma")
        d.draw_text(draw, (d.WIDTH / 2, 110), self._t("welcome.how_many"), 17, d.MUTED, anchor="ma")
        d.draw_option(draw, (16, 136, 114, 180), "12", self.words == 12, 26)
        d.draw_option(draw, (126, 136, 224, 180), "24", self.words == 24, 26)
        d.draw_text(
            draw, (d.WIDTH / 2, 192), self._t("key2.start_over"), 14, d.MUTED, anchor="ma"
        )
        d.draw_help(draw, self._t("welcome.help"))

    def _draw_tiradas(self, image, draw) -> None:
        count = len(self._rolls)
        total = self.total_rolls
        # Contador grande.
        d.draw_text(draw, (12, 6), str(count), 36, d.ACCENT, bold=True)
        number_width = d.text_width(str(count), 36) + 2
        d.draw_text(draw, (12 + number_width + 8, 20), self._t("rolls.of_total", total=total), 22, d.TEXT)
        d.draw_text(draw, (228, 10), self._t("rolls.for"), 14, d.MUTED, anchor="ra")
        d.draw_text(draw, (228, 27), self._t("rolls.words", words=self.words), 14, d.MUTED, anchor="ra")
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
        d.draw_help(draw, self._t("rolls.help"))

    def _draw_revisar_tiradas(self, image, draw) -> None:
        total = len(self._rolls)
        pages = (total + REVIEW_PER_PAGE - 1) // REVIEW_PER_PAGE
        page = self._review_index // REVIEW_PER_PAGE
        first = page * REVIEW_PER_PAGE
        last = min(total, first + REVIEW_PER_PAGE)
        d.draw_text(draw, (12, 6), self._t("review.title", first=first + 1, last=last), 18, d.ACCENT, bold=True)
        d.draw_text(draw, (228, 8), f"{page + 1}/{pages}", 16, d.MUTED, anchor="ra")
        if self._editing:
            note = self._t("review.editing", n=self._review_index + 1)
            d.draw_text(draw, (12, 30), note, d.fit_size(note, 14, d.WIDTH - 24), d.OK)
        else:
            d.draw_text(draw, (12, 30), self._t("review.compare"), 14, d.MUTED)
        col_w, row_h = 36, 31
        left, top = 50, 52
        for i in range(first, last):
            offset = i - first
            row, col = divmod(offset, REVIEW_COLS)
            y = top + row * row_h
            if col == 0:
                d.draw_text(draw, (40, y + 13), str(i + 1), 14, d.MUTED, anchor="rm")
            cx = left + col * col_w + col_w / 2
            cell = (cx - 15, y, cx + 15, y + 27)
            color = d.TEXT
            if i == self._review_index:
                fill = d.OK if self._editing else d.ACCENT
                draw.rounded_rectangle(cell, radius=6, fill=fill)
                color = d.ACCENT_TEXT
            d.draw_text(draw, (cx, y + 14), self._rolls[i], 24, color, bold=True, anchor="mm")
        if self._editing:
            d.draw_help(draw, self._t("review.help_editing"))
        else:
            d.draw_help(draw, self._t("review.help"))

    def _draw_confirmar_tiradas(self, image, draw) -> None:
        total = len(self._rolls)
        y = d.draw_paragraph(
            draw, 8, self._t("confirm.question", total=total), 18, d.ACCENT,
            bold=False, center=True,
        )
        d.draw_paragraph(
            draw, y + 8,
            self._t("confirm.body"),
            15, d.TEXT, center=True,
        )
        options_top = 164
        d.draw_option(draw, (10, options_top, 116, options_top + 44), self._t("confirm.yes"), self._final_choice == 0, 17)
        d.draw_option(draw, (124, options_top, 230, options_top + 44), self._t("confirm.no"), self._final_choice == 1, 17)
        d.draw_help(draw, self._t("help.choose_accept"))

    def _draw_tiradas_raras(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 14, self._t("bad.title"), 22, d.DANGER, bold=True, center=True)
        y = d.draw_paragraph(draw, y + 8, i18n.rolls_problem(self._rolls_problem, self.lang), 16, d.TEXT, center=True)
        d.draw_paragraph(
            draw, y + 8,
            self._t("bad.body"),
            15, d.MUTED, center=True,
        )
        d.draw_help(draw, self._t("bad.help"))

    def _draw_aviso(self, image, draw) -> None:
        d.draw_text(draw, (d.WIDTH / 2, 12), "!", 40, d.DANGER, bold=True, anchor="ma")
        y = d.draw_paragraph(draw, 62, self._t("warning.title"), 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 10,
            self._t("warning.body", n=len(self._mnemonic)),
            16, center=True,
        )
        d.draw_help(draw, self._t("warning.help"))

    def _draw_frase(self, image, draw) -> None:
        total = len(self._mnemonic)
        first = self._page * WORDS_PER_PAGE
        d.draw_text(
            draw, (12, 6), self._t("phrase.title", first=first + 1, last=first + WORDS_PER_PAGE, total=total),
            16, d.ACCENT, bold=True,
        )
        hint = {
            PHRASE_FIRST: "phrase.copy",
            PHRASE_FIX: "phrase.fix",
            PHRASE_REVIEW: "phrase.review",
        }[self._phrase_mode]
        hint = self._t(hint)
        d.draw_text(draw, (12, 28), hint, 14, d.MUTED)
        top, step = 56, 40
        for i in range(WORDS_PER_PAGE):
            number = first + i + 1
            y = top + i * step
            d.draw_text(draw, (54, y + 17), f"{number}", 22, d.MUTED, anchor="rm")
            d.draw_text(draw, (64, y + 17), self._mnemonic[number - 1], 30, d.TEXT, bold=True, anchor="lm")
        if self._phrase_mode == PHRASE_FIX:
            help_text = self._t("phrase.help_fix")
        elif self._phrase_mode == PHRASE_REVIEW:
            help_text = self._t("phrase.help_review")
        elif self._page < self._pages() - 1:
            help_text = self._t("phrase.help_next")
        else:
            help_text = self._t("phrase.help_last")
        d.draw_help(draw, help_text)

    def _draw_examen(self, image, draw) -> None:
        position = self._exam_positions[self._exam_index]
        d.draw_text(
            draw, (12, 6), self._t("exam.title", n=self._exam_index + 1, total=len(self._exam_positions)),
            16, d.ACCENT, bold=True,
        )
        question = self._t("exam.question", position=position)
        d.draw_text(draw, (12, 30), question, d.fit_size(question, 20, d.WIDTH - 24), bold=True)
        top, height, gap = 60, 31, 4
        for i, option in enumerate(self._exam_options):
            y = top + i * (height + gap)
            d.draw_option(draw, (12, y, 228, y + height), option, i == self._exam_choice, 22)
        d.draw_text(draw, (d.WIDTH / 2, 200), self._t("exam.not_on_paper"), 14, d.MUTED, anchor="ma")
        d.draw_help(draw, self._t("exam.help"))

    def _draw_examen_fallado(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 40, self._t("fail.title", position=self._failed_position), 22, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14,
            self._t("fail.body"),
            17, center=True,
        )
        d.draw_help(draw, self._t("fail.help"))

    def _draw_examen_aprobado(self, image, draw) -> None:
        title = self._t("passed.title")
        d.draw_text(draw, (d.WIDTH / 2, 8), title, d.fit_size(title, 24, d.WIDTH - 16), d.OK, bold=True, anchor="ma")
        y = d.draw_paragraph(draw, 42, self._t("passed.match"), 17, center=True)
        d.draw_paragraph(
            draw, y + 4,
            self._t("passed.note"),
            15, d.MUTED, center=True,
        )
        d.draw_option(draw, (12, 134, 228, 166), self._t("passed.review"), self._passed_choice == 0, 18)
        d.draw_option(draw, (12, 174, 228, 206), self._t("passed.continue"), self._passed_choice == 1, 18)
        d.draw_help(draw, self._t("passed.help"))

    def _draw_calculando(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 70, self._t("deriving.title"), 20, center=True)
        d.draw_paragraph(
            draw, y + 10, self._t("deriving.body"),
            16, d.MUTED, center=True,
        )

    def _draw_no_coincide(self, image, draw) -> None:
        y = d.draw_paragraph(draw, 30, self._t("mismatch.title"), 24, d.DANGER, bold=True, center=True)
        d.draw_paragraph(
            draw, y + 14,
            self._t("mismatch.body"),
            17, center=True,
        )

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
        # Con el zpub no se enseña la huella maestra: el zpub no la lleva y el
        # iPhone no la mostraría igual. Con el descriptor sí va dentro.
        if self.qr_mode == "zpub":
            info = self._t("qr.zpub")
        else:
            info = self._t("qr.descriptor", fingerprint=self.account.fingerprint)
        text_y = d.HEIGHT - footer / 2
        d.draw_text(draw, (6, text_y), info, 14, d.TEXT, anchor="lm")
        d.draw_text(draw, (d.WIDTH - 6, text_y), "KEY1 ⇄", 14, d.ACCENT, anchor="rm")

    def _draw_comprobacion(self, image, draw) -> None:
        title = self._t("check.title")
        d.draw_text(draw, (d.WIDTH / 2, 4), title, d.fit_size(title, 18, d.WIDTH - 16), d.ACCENT, bold=True, anchor="ma")
        label = self._t("check.first_address")
        d.draw_text(draw, (12, 30), label, d.fit_size(label, 15, d.WIDTH - 24), d.MUTED)
        # Bloques de 4 en tres columnas fijas, alineados a la izquierda.
        blocks = d.blocks_of_four(self._first_address)
        col_x = (12, 88, 164)
        for i, block in enumerate(blocks):
            row, col = divmod(i, 3)
            size = d.fit_size(block, 20, 70)
            d.draw_text(draw, (col_x[col], 52 + row * 25), block, size)
        label = self._t("check.fingerprint")
        d.draw_text(draw, (12, 154), label, d.fit_size(label, 14, d.WIDTH - 24), d.MUTED)
        d.draw_mono(draw, (12, 172), self.account.fingerprint, 22, bold=True)
        note = self._t("check.zpub_note")
        d.draw_text(draw, (12, 199), note, d.fit_size(note, 14, d.WIDTH - 24), d.MUTED)
        d.draw_help(draw, self._t("check.help"))

    def _draw_fin(self, image, draw) -> None:
        title = self._t("end.title")
        d.draw_text(draw, (d.WIDTH / 2, 20), title, d.fit_size(title, 26, d.WIDTH - 16), d.ACCENT, bold=True, anchor="ma")
        y = d.draw_paragraph(
            draw, 64, self._t("end.body"), 17, center=True,
        )
        d.draw_paragraph(
            draw, y + 10,
            self._t("end.paper"),
            15, d.MUTED, center=True,
        )
        d.draw_help(draw, self._t("key2.start_over"))
