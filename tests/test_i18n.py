"""Pruebas de los idiomas de la pantalla (en, es, pt).

- Las tres tablas tienen las mismas claves y los mismos huecos.
- En cada pantalla y en cada idioma, todo el texto cabe en 240x240: nada se
  sale, nada se pisa con otro texto, con un botón, un dado, el QR o la barra
  de ayuda, y cada etiqueta cabe en su botón.
- El español sale idéntico al de antes: las capturas de docs/capturas/ se
  regeneran píxel a píxel.
- Las palabras de la frase y el QR son los mismos en todos los idiomas.

Solo usan las tiradas de PRUEBA fijas, que son públicas.
"""

from __future__ import annotations

import contextlib
import io
import importlib.util
import itertools
import pathlib
from dataclasses import dataclass

import PIL
import pytest
from PIL import Image

from coldwallet import core
from coldwallet.ui import app as ui
from coldwallet.ui import drawing as d
from coldwallet.ui import i18n

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST_ROLLS_24 = "123456" * 16 + "123"
TEST_ROLLS_12 = TEST_ROLLS_24[:50]
LANGS = i18n.LANGUAGES

# Las capturas guardadas se hicieron con esta versión de Pillow (la fijada en
# requirements-dev.txt). Con otra, el suavizado de las letras puede cambiar
# algún píxel; entonces esas comparaciones se saltan.
SCREENSHOT_PILLOW = "13.0.0"


def _load_capturas():
    spec = importlib.util.spec_from_file_location("capturas", ROOT / "scripts" / "capturas.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- tablas de textos -------------------------------------------------------


def test_languages_and_default():
    assert set(i18n.STRINGS) == {"en", "es", "pt"} == set(LANGS)
    assert i18n.DEFAULT_LANGUAGE == "es"
    assert ui.WalletApp().lang == "es"


@pytest.mark.parametrize("lang", ["en", "pt"])
def test_every_key_in_every_language_with_same_placeholders(lang):
    spanish = i18n.STRINGS["es"]
    other = i18n.STRINGS[lang]
    assert set(other) == set(spanish)
    for key, text in spanish.items():
        assert i18n.placeholders(other[key]) == i18n.placeholders(text), key
        assert other[key].strip() == other[key] and other[key], key


def test_unknown_language_is_rejected():
    with pytest.raises(ValueError):
        i18n.check_language("fr")
    with pytest.raises(ValueError):
        ui.WalletApp("fr")
    with pytest.raises(KeyError):
        i18n.t("no.existe", "en")


def test_core_rolls_problems_are_all_translated():
    """Los dos avisos del núcleo tienen traducción; en español quedan igual."""
    messages = {
        core.rolls_quality_problem("1" * 99),
        core.rolls_quality_problem("1" * 8 + TEST_ROLLS_24[8:]),
        core.rolls_quality_problem("1" * 50),
    }
    assert messages == set(i18n.CORE_ROLLS_PROBLEMS)
    for message in messages:
        assert i18n.rolls_problem(message, "es") == message
        for lang in ("en", "pt"):
            assert i18n.rolls_problem(message, lang) != message
    assert i18n.rolls_problem("otro aviso", "en") == "otro aviso"


def test_language_survives_reset():
    app = ui.WalletApp("pt")
    app.handle(ui.PRESS)
    app.handle(ui.KEY2)
    app.handle(ui.RIGHT)
    app.handle(ui.PRESS)
    assert app.screen == ui.WELCOME and app.lang == "pt"


# --- todo cabe en la pantalla ---------------------------------------------------


@dataclass
class _Text:
    text: str
    bbox: tuple[int, int, int, int]
    container: tuple[int, int, int, int] | None


def _overlap(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _inside(inner, outer) -> bool:
    return inner[0] >= outer[0] and inner[1] >= outer[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


HELP_BAR = (0, d.HEIGHT - 22, d.WIDTH, d.HEIGHT)
# Margen mínimo a los lados: el que ya deja el español en su texto más ancho.
SIDE_MARGIN = 4


class _Layout:
    """Apunta dónde cae cada texto y cada elemento al pintar una pantalla."""

    def __init__(self) -> None:
        self.texts: list[_Text] = []
        self.blocks: list[tuple[int, int, int, int]] = []  # botones, dados, QR, barra de ayuda
        self._container = None
        self._group = None

    def clear(self) -> None:
        self.texts.clear()
        self.blocks.clear()

    def add_text(self, bbox, text) -> None:
        if not text or bbox[0] == bbox[2]:
            return
        if self._group is not None:
            self._group.append(bbox)
            return
        self.texts.append(_Text(text, bbox, self._container))

    def problems(self) -> list[str]:
        found = []
        for t in self.texts:
            if not _inside(t.bbox, (SIDE_MARGIN, 0, d.WIDTH - SIDE_MARGIN, d.HEIGHT)):
                found.append(f"se sale de la pantalla o toca el borde: {t.text!r} {t.bbox}")
            if t.container is not None:
                margin = 1 if t.container == HELP_BAR else 3
                inner = (t.container[0] + margin, t.container[1] + 1,
                         t.container[2] - margin, t.container[3] - 1)
                if not _inside(t.bbox, inner):
                    found.append(f"no cabe en su recuadro: {t.text!r} {t.bbox} en {t.container}")
        for a, b in itertools.combinations(self.texts, 2):
            if _overlap(a.bbox, b.bbox):
                found.append(f"textos pisados: {a.text!r} {a.bbox} y {b.text!r} {b.bbox}")
        for t in self.texts:
            for block in self.blocks:
                if block != t.container and _overlap(t.bbox, block):
                    found.append(f"texto sobre un elemento: {t.text!r} {t.bbox} y {block}")
        return found


@pytest.fixture
def layout(monkeypatch):
    """Envuelve las funciones de dibujo para apuntar el sitio de cada cosa."""
    record = _Layout()
    real = {name: getattr(d, name) for name in
            ("draw_text", "draw_option", "draw_help", "draw_mono", "draw_die", "draw_qr")}

    def draw_text(draw, xy, text, size, fill=d.TEXT, bold=False, anchor="la"):
        stroke = 1 if bold and size >= 20 else 0
        bbox = draw.textbbox(xy, text, font=d.font(size), anchor=anchor, stroke_width=stroke)
        record.add_text(bbox, text)
        real["draw_text"](draw, xy, text, size, fill, bold, anchor)

    def draw_option(draw, box, label, selected, size=18):
        record.blocks.append(tuple(box))
        record._container = tuple(box)
        try:
            real["draw_option"](draw, box, label, selected, size)
        finally:
            record._container = None

    def draw_help(draw, text):
        record.blocks.append(HELP_BAR)
        record._container = HELP_BAR
        try:
            real["draw_help"](draw, text)
        finally:
            record._container = None

    def draw_mono(draw, xy, text, size, fill=d.TEXT, bold=False):
        # Una sola caja para toda la huella: las letras van en casillas pegadas.
        record._group = []
        try:
            result = real["draw_mono"](draw, xy, text, size, fill, bold)
            boxes = record._group
        finally:
            record._group = None
        record.add_text(_union(boxes), text)
        return result

    def draw_die(draw, x, y, size, face, selected=False):
        pad = 5 if selected else 0
        record.blocks.append((x - pad, y - pad, x + size + pad, y + size + pad))
        real["draw_die"](draw, x, y, size, face, selected)

    def draw_qr(image, matrix, x0, y0, px):
        side = real["draw_qr"](image, matrix, x0, y0, px)
        record.blocks.append((x0, y0, x0 + side, y0 + side))
        return side

    for name, wrapper in (("draw_text", draw_text), ("draw_option", draw_option),
                          ("draw_help", draw_help), ("draw_mono", draw_mono),
                          ("draw_die", draw_die), ("draw_qr", draw_qr)):
        monkeypatch.setattr(d, name, wrapper)

    # El diálogo de empezar de nuevo tapa toda la pantalla antes de pintarse.
    real_dialog = ui.WalletApp._draw_reset_dialog

    def draw_reset_dialog(self, draw):
        record.clear()
        real_dialog(self, draw)

    monkeypatch.setattr(ui.WalletApp, "_draw_reset_dialog", draw_reset_dialog)
    return record


class _Checker:
    """Pinta pantallas como el simulador (WalletApp.render) y junta los problemas."""

    def __init__(self, record: _Layout) -> None:
        self.record = record
        self.problems: list[str] = []
        self.screens: set[str] = set()

    def render(self, app_or_render, where: str = "") -> None:
        self.record.clear()
        if isinstance(app_or_render, ui.WalletApp):
            image = app_or_render.render()
            name = app_or_render.screen + ("+reinicio" if app_or_render.confirm_reset_open else "")
        else:
            image = app_or_render()
            name = where
        assert image.size == (d.WIDTH, d.HEIGHT)
        self.screens.add(name)
        self.problems += [f"[{name} {where}] {p}" for p in self.record.problems()]


def _press(app, *events):
    for event in events:
        app.handle(event)


def _enter(app, rolls, check=None):
    for roll in rolls:
        _press(app, *ui.moves_to_face(app.cursor_face, int(roll)), ui.PRESS)
        if check is not None and app.screen == ui.ROLLS:
            check.render(app, f"{app.rolls_count} tiradas")


def _answer(app, mnemonic, wrong=False):
    correct = mnemonic[app.exam_position - 1]
    target = next(i for i, w in enumerate(app.exam_options) if (w != correct) == wrong)
    while app.exam_choice != target:
        _press(app, ui.DOWN)
    _press(app, ui.PRESS)


def _walk_every_screen(lang, check: _Checker, words: int) -> None:
    """Recorre todas las pantallas con los números más largos (99, 24…)."""
    rolls = TEST_ROLLS_24 if words == 24 else TEST_ROLLS_12
    mnemonic = core.mnemonic_from_rolls(rolls, words)
    app = ui.WalletApp(lang)
    if words == 12:
        _press(app, ui.LEFT)
    check.render(app)
    _press(app, ui.KEY2)
    check.render(app)
    _press(app, ui.RIGHT)
    check.render(app, "sí elegido")
    _press(app, ui.KEY2)
    _press(app, ui.PRESS)
    check.render(app, "0 tiradas")
    _enter(app, rolls, check)
    # Revisión: todas las páginas, y cambiando la última tirada.
    check.render(app)
    _press(app, *[ui.DOWN] * 30, *[ui.RIGHT] * 10)
    check.render(app, "última página")
    _press(app, ui.PRESS)
    check.render(app, "cambiando la última")
    _press(app, ui.KEY3)
    _press(app, *[ui.UP] * 5)
    check.render(app, "página anterior")
    _press(app, ui.KEY1)
    check.render(app, "no, revisar")
    _press(app, ui.LEFT)
    check.render(app, "sí, seguir")
    _press(app, ui.PRESS)
    check.render(app)  # aviso
    _press(app, ui.PRESS)
    while app.screen == ui.PHRASE:
        check.render(app, f"página {app.phrase_page + 1}")
        _press(app, ui.RIGHT)
    # Examen: todas las preguntas; falla la última para ver «Revisa la palabra 24».
    while app.exam_position < words:
        check.render(app, f"pregunta {app.exam_position}")
        _answer(app, mnemonic)
    check.render(app, f"pregunta {app.exam_position}")
    _answer(app, mnemonic, wrong=True)
    check.render(app)
    _press(app, ui.PRESS)
    check.render(app, "corregir")
    _press(app, ui.PRESS)
    _answer(app, mnemonic)
    check.render(app, "repasar elegido")
    _press(app, ui.PRESS)
    while app.screen == ui.PHRASE and app.phrase_page < words // ui.WORDS_PER_PAGE - 1:
        check.render(app, f"repaso {app.phrase_page + 1}")
        _press(app, ui.RIGHT)
    check.render(app, "repaso última")
    _press(app, ui.PRESS)
    _press(app, ui.DOWN)
    check.render(app, "seguir al QR elegido")
    _press(app, ui.PRESS)
    check.render(app)  # calculando
    app.run_pending_work()
    check.render(app, "zpub")
    _press(app, ui.KEY1)
    check.render(app, "descriptor")
    _press(app, ui.PRESS)
    check.render(app)  # comprobación
    _press(app, ui.PRESS)
    check.render(app)  # fin
    _press(app, ui.KEY2)
    check.render(app)


def _walk_blocked_screens(lang, check: _Checker) -> None:
    for rolls in ("1" * 99, "1" * 8 + TEST_ROLLS_24[8:]):
        app = ui.WalletApp(lang)
        _press(app, ui.PRESS)
        _enter(app, rolls)
        _press(app, ui.KEY1, ui.LEFT, ui.PRESS)
        assert app.screen == ui.ROLLS_BAD
        check.render(app, rolls[:10])
    app = ui.WalletApp(lang)
    app._fail_mismatch()  # noqa: SLF001
    check.render(app)
    check.render(lambda: ui.WalletApp.render_error(lang), "error")
    check.render(lambda: ui.WalletApp.render_network_warning(lang), "hay red")


@pytest.mark.parametrize("lang", LANGS)
def test_every_screen_fits_without_clipping_or_overlap(lang, layout):
    check = _Checker(layout)
    for words in (24, 12):
        _walk_every_screen(lang, check, words)
    _walk_blocked_screens(lang, check)
    every_screen = {getattr(ui, name) for name in (
        "WELCOME", "ROLLS", "ROLLS_CONFIRM", "ROLLS_FINAL", "ROLLS_BAD", "WARNING", "PHRASE",
        "EXAM", "EXAM_FAIL", "EXAM_PASSED", "DERIVING", "MISMATCH", "QR", "CHECK", "END")}
    assert every_screen <= check.screens
    assert {"error", "hay red"} <= check.screens
    assert any(name.endswith("+reinicio") for name in check.screens)
    assert check.problems == []


@pytest.mark.parametrize("lang", LANGS)
def test_simulator_banner_and_screenshot_band_fit(lang):
    import sim

    capturas = _load_capturas()
    for text, size, width in (
        (i18n.t("sim.banner", lang), 18, 480 - 12),
        (i18n.t("shots.band", lang), 22, 480 - 16),
    ):
        assert d.text_width(text, d.fit_size(text, size, width)) <= width
    frame = ui.WalletApp(lang).render().resize((480, 480))
    assert sim.with_banner(frame, lang).size == (480, 480 + sim.BANNER)
    assert capturas.with_band(ui.WalletApp(lang).render(), lang).size == (480, 480 + capturas.BAND)


# --- lo que no cambia con el idioma ---------------------------------------------


def test_phrase_words_and_qr_are_the_same_in_every_language(monkeypatch):
    """La frase son siempre palabras BIP39 en inglés y el QR no depende del idioma."""
    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    payloads = {}
    for lang in LANGS:
        shown = []
        real = d.draw_text

        def spy(draw, xy, text, size, *args, **kwargs):
            shown.append(text)
            real(draw, xy, text, size, *args, **kwargs)

        monkeypatch.setattr(d, "draw_text", spy)
        app = ui.WalletApp(lang)
        _press(app, ui.PRESS)
        _enter(app, TEST_ROLLS_24)
        _press(app, ui.KEY1, ui.LEFT, ui.PRESS, ui.PRESS)
        while app.screen == ui.PHRASE:
            app.render()
            _press(app, ui.RIGHT)
        monkeypatch.setattr(d, "draw_text", real)
        assert [w for w in shown if w in mnemonic] == mnemonic
        while app.screen == ui.EXAM:
            assert set(app.exam_options) <= set(mnemonic)
            _answer(app, mnemonic)
        _press(app, ui.DOWN, ui.PRESS)
        app.run_pending_work()
        payloads[lang] = (app.qr_payload, app.account.fingerprint)
    assert len(set(payloads.values())) == 1


# --- el español no cambia ---------------------------------------------------------


def _pixels(image: Image.Image) -> bytes:
    return image.convert("RGB").tobytes()


@pytest.mark.skipif(PIL.__version__ != SCREENSHOT_PILLOW,
                    reason=f"las capturas se hicieron con Pillow {SCREENSHOT_PILLOW}")
@pytest.mark.parametrize("lang", LANGS)
def test_saved_screenshots_match_the_code(lang):
    """Las capturas guardadas son exactamente lo que pinta el código.

    En español también se comparan con docs/capturas/, las de antes de añadir
    los idiomas: el español tiene que salir idéntico.
    """
    capturas = _load_capturas()
    folder = ROOT / "docs" / "screenshots" / lang
    with contextlib.closing(capturas.shots(lang)) as shots:
        made = list(shots)
    assert len(made) == 26
    assert sorted(p.name for p in folder.glob("*.png")) == sorted(f"{en}.png" for _, en, _ in made)
    for name_es, name_en, image in made:
        with Image.open(folder / f"{name_en}.png") as saved:
            assert _pixels(saved) == _pixels(image), name_en
        if lang == "es":
            with Image.open(ROOT / "docs" / "capturas" / f"{name_es}.png") as before:
                assert _pixels(before) == _pixels(image), name_es
    assert core.quiz_options.__module__ == "coldwallet.core"  # se deja como estaba


# --- arranque con --lang ---------------------------------------------------------


def test_main_lang_option(monkeypatch):
    import main
    import sim
    from coldwallet import hw

    assert main.parse_args(["--hw"]).lang == "es"  # el servicio de systemd no lo pasa
    assert main.parse_args(["--sim", "--lang", "pt"]).lang == "pt"
    assert main.parse_args(["--lang=en", "--otro"]).lang == "en"
    with pytest.raises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
        main.parse_args(["--lang", "fr"])
    calls = []
    monkeypatch.setattr(hw, "run", lambda lang="es": calls.append(("hw", lang)))
    monkeypatch.setattr(sim, "run", lambda lang="es": calls.append(("sim", lang)))
    main.main(["--hw"])
    main.main(["--hw", "--lang", "en"])
    main.main(["--sim", "--lang", "pt"])
    assert calls == [("hw", "es"), ("hw", "en"), ("sim", "pt")]


def test_hw_run_shows_the_chosen_language(monkeypatch):
    from coldwallet import hw

    class FakeDisplay:
        def __init__(self):
            self.frames = []

        def show(self, image):
            self.frames.append(image.copy())

        def off(self):
            pass

    display = FakeDisplay()
    monkeypatch.setattr(hw.signal, "signal", lambda *args: None)
    monkeypatch.setattr(hw, "ST7789", lambda: display)
    monkeypatch.setattr(hw, "network_interfaces", lambda: ["wlan0"])
    monkeypatch.setattr(hw, "_wait_forever", lambda _display: None)
    hw.run("en")
    english = ui.WalletApp.render_network_warning("en").tobytes()
    assert display.frames[-1].tobytes() == english
    assert english != ui.WalletApp.render_network_warning().tobytes()
    with pytest.raises(ValueError):
        hw.run("fr")
