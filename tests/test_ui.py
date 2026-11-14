"""Pruebas de la interfaz: recorrido completo por eventos, QR, borrado y examen.

Solo usan las tiradas de PRUEBA fijas, que son públicas.
"""

from __future__ import annotations

import builtins
import io
import logging
import os
import pathlib
import re

import pytest

try:  # Lector de QR opcional, solo para las pruebas (pip install zxing-cpp).
    import zxingcpp
except ImportError:
    zxingcpp = None

from coldwallet import core
from coldwallet.ui import app as ui
from coldwallet.ui import drawing as d

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEST_ROLLS_24 = "123456" * 16 + "123"
TEST_ROLLS_12 = TEST_ROLLS_24[:50]


def press(app, *events):
    for event in events:
        app.handle(event)


def enter_roll(app, face):
    press(app, *ui.moves_to_face(app.cursor_face, int(face)), ui.PRESS)


def enter_rolls(app, rolls):
    for roll in rolls:
        enter_roll(app, roll)


def answer(app, mnemonic, wrong=False):
    correct = mnemonic[app.exam_position - 1]
    options = app.exam_options
    assert correct in options and len(options) == 4
    target = next(i for i, w in enumerate(options) if (w != correct) == wrong)
    while app.exam_choice != target:
        press(app, ui.DOWN)
    press(app, ui.PRESS)


def walk_to_qr(app, words=24):
    """Recorrido completo, desde la bienvenida hasta el QR."""
    rolls = TEST_ROLLS_24 if words == 24 else TEST_ROLLS_12
    mnemonic = core.mnemonic_from_rolls(rolls, words)
    app.render()
    if words == 12:
        press(app, ui.LEFT)
    press(app, ui.PRESS)
    assert app.screen == ui.ROLLS
    for roll in rolls:
        app.render()
        enter_roll(app, roll)
    assert app.screen == ui.ROLLS_CONFIRM
    app.render()
    press(app, ui.UP, ui.PRESS)
    assert app.screen == ui.WARNING and app.rolls_count == 0
    app.render()
    press(app, ui.PRESS)
    while app.screen == ui.PHRASE:
        app.render()
        press(app, ui.RIGHT)
    for _ in range(ui.EXAM_QUESTIONS):
        assert app.screen == ui.EXAM
        app.render()
        answer(app, mnemonic)
    assert app.screen == ui.EXAM_PASSED
    app.render()
    press(app, ui.PRESS)
    assert app.has_pending_work and app.screen == ui.DERIVING
    app.render()
    app.run_pending_work()
    assert app.screen == ui.QR
    return mnemonic


# --- utilidades -----------------------------------------------------------


@pytest.mark.parametrize("start", range(1, 7))
@pytest.mark.parametrize("target", range(1, 7))
def test_moves_to_face_reach_target(start, target):
    app = ui.WalletApp()
    press(app, ui.PRESS)
    # Llevar el cursor a la cara de inicio y luego a la de destino.
    press(app, *ui.moves_to_face(app.cursor_face, start))
    assert app.cursor_face == start
    press(app, *ui.moves_to_face(start, target))
    assert app.cursor_face == target


def test_rendered_image_is_240_rgb():
    image = ui.WalletApp().render()
    assert image.size == (240, 240) and image.mode == "RGB"


def test_unknown_event_rejected():
    with pytest.raises(ValueError):
        ui.WalletApp().handle("A")


# --- recorrido completo y QR -----------------------------------------------


def _sample_matrix(image, geometry):
    """Lee los módulos del QR en la imagen (centro de cada módulo)."""
    px, n = geometry["px"], geometry["modules"]
    x0 = geometry["x0"] + d.QR_BORDER * px
    y0 = geometry["y0"] + d.QR_BORDER * px
    pixels = image.load()
    return [
        [pixels[x0 + c * px + px // 2, y0 + r * px + px // 2] == d.BLACK for c in range(n)]
        for r in range(n)
    ]


def _check_qr_image(image, geometry, payload):
    """La imagen contiene exactamente el QR del texto esperado, con su borde."""
    expected = d.qr_matrix(payload, geometry["level"])
    assert len(expected) == geometry["modules"]
    assert _sample_matrix(image, geometry) == expected
    # Borde blanco de 4 módulos alrededor.
    px, n = geometry["px"], geometry["modules"]
    side = (n + 2 * d.QR_BORDER) * px
    pixels = image.load()
    for i in range(side):
        for x, y in (
            (geometry["x0"] + i, geometry["y0"] + px),
            (geometry["x0"] + i, geometry["y0"] + side - 1 - px),
            (geometry["x0"] + px, geometry["y0"] + i),
            (geometry["x0"] + side - 1 - px, geometry["y0"] + i),
        ):
            assert pixels[x, y] == d.WHITE
    # Cabe en la pantalla y los módulos tienen al menos 3 píxeles.
    assert geometry["x0"] >= 0 and geometry["x0"] + side <= 240
    assert geometry["y0"] + side <= 240 - 20
    assert px >= 3


def _decode(image):
    """Decodifica el QR con zxing-cpp (solo en pruebas)."""
    big = image.resize((image.width * 3, image.height * 3))
    results = zxingcpp.read_barcodes(big)
    return [r.text for r in results]


@pytest.mark.parametrize("words", [24, 12])
def test_full_walk_qr_is_exactly_zpub_then_descriptor(words):
    app = ui.WalletApp()
    mnemonic = walk_to_qr(app, words)
    info = core.derive_account(mnemonic)
    assert not app.has_phrase  # la frase ya no está en memoria de la app

    image = app.render()
    assert app.qr_payload == info.zpub
    _check_qr_image(image, app.qr_geometry, info.zpub)
    if zxingcpp is not None:
        assert _decode(image) == [info.zpub]

    press(app, ui.KEY1)
    image = app.render()
    assert app.qr_payload == info.descriptor
    _check_qr_image(image, app.qr_geometry, info.descriptor)
    if zxingcpp is not None:
        assert _decode(image) == [info.descriptor]

    press(app, ui.KEY1)
    assert app.qr_payload == info.zpub

    press(app, ui.PRESS)
    assert app.screen == ui.CHECK
    app.render()
    press(app, ui.PRESS)
    assert app.screen == ui.END
    app.render()


@pytest.mark.skipif(zxingcpp is None, reason="sin lector de QR (pip install zxing-cpp)")
def test_qr_decodes_with_real_reader():
    """Un lector de QR de verdad lee en la imagen exactamente el zpub y el descriptor."""
    app = ui.WalletApp()
    mnemonic = walk_to_qr(app)
    info = core.derive_account(mnemonic)
    assert _decode(app.render()) == [info.zpub]
    press(app, ui.KEY1)
    assert _decode(app.render()) == [info.descriptor]


def test_qr_modules_are_big():
    """El zpub y el descriptor se pintan con módulos de 4 píxeles."""
    app = ui.WalletApp()
    walk_to_qr(app)
    app.render()
    assert app.qr_geometry["px"] == 4
    press(app, ui.KEY1)
    app.render()
    assert app.qr_geometry["px"] == 4


# --- tiradas -------------------------------------------------------------


def test_key3_deletes_last_roll():
    app = ui.WalletApp()
    press(app, ui.PRESS)
    press(app, ui.KEY3)  # sin tiradas no pasa nada
    assert app.rolls_count == 0
    enter_rolls(app, "65")
    assert app.rolls_count == 2
    press(app, ui.KEY3)
    assert app.rolls_count == 1
    press(app, ui.KEY3)
    assert app.rolls_count == 0
    # Se borró justo la última: con un error corregido sale el mismo zpub.
    enter_rolls(app, TEST_ROLLS_24[:10])
    enter_roll(app, "6")
    press(app, ui.KEY3)
    enter_rolls(app, TEST_ROLLS_24[10:])
    assert app.screen == ui.ROLLS_CONFIRM
    press(app, ui.UP, ui.PRESS, ui.PRESS)
    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    while app.screen == ui.PHRASE:
        press(app, ui.RIGHT)
    for _ in range(ui.EXAM_QUESTIONS):
        answer(app, mnemonic)
    press(app, ui.PRESS)
    app.run_pending_work()
    assert app.qr_payload == core.derive_account(mnemonic).zpub


def test_confirm_back_and_key3_on_confirm():
    app = ui.WalletApp()
    press(app, ui.LEFT, ui.PRESS)  # 12 palabras
    enter_rolls(app, TEST_ROLLS_12)
    assert app.screen == ui.ROLLS_CONFIRM
    press(app, ui.PRESS)  # por defecto, «No, volver»
    assert app.screen == ui.ROLLS and app.rolls_count == 50
    press(app, ui.PRESS)  # completo: no añade, vuelve a la confirmación
    assert app.screen == ui.ROLLS_CONFIRM and app.rolls_count == 50
    press(app, ui.KEY3)
    assert app.screen == ui.ROLLS and app.rolls_count == 49


# --- examen ----------------------------------------------------------------


def test_exam_blocks_when_failing():
    app = ui.WalletApp()
    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    press(app, ui.PRESS)
    enter_rolls(app, TEST_ROLLS_24)
    press(app, ui.UP, ui.PRESS, ui.PRESS)
    while app.screen == ui.PHRASE:
        press(app, ui.RIGHT)
    for attempt in range(5):
        assert app.screen == ui.EXAM
        failed = app.exam_position
        answer(app, mnemonic, wrong=True)
        assert app.screen == ui.EXAM_FAIL
        app.render()
        for event in (ui.UP, ui.DOWN, ui.LEFT, ui.RIGHT, ui.KEY1, ui.KEY3):
            press(app, event)
            assert app.screen == ui.EXAM_FAIL
        assert app.account is None
        press(app, ui.PRESS)
        # Vuelve a la página de la frase donde está la palabra fallada.
        assert app.screen == ui.PHRASE
        assert app.phrase_page == (failed - 1) // ui.WORDS_PER_PAGE
        while app.screen == ui.PHRASE:
            press(app, ui.RIGHT)
    # Aprobar después de fallar sí deja avanzar.
    for _ in range(ui.EXAM_QUESTIONS):
        answer(app, mnemonic)
    assert app.screen == ui.EXAM_PASSED


def test_exam_positions_are_distinct():
    app = ui.WalletApp()
    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    press(app, ui.PRESS)
    enter_rolls(app, TEST_ROLLS_24)
    press(app, ui.UP, ui.PRESS, ui.PRESS)
    while app.screen == ui.PHRASE:
        press(app, ui.RIGHT)
    seen = []
    for _ in range(ui.EXAM_QUESTIONS):
        seen.append(app.exam_position)
        answer(app, mnemonic)
    assert len(set(seen)) == ui.EXAM_QUESTIONS and seen == sorted(seen)


# --- empezar de nuevo ------------------------------------------------------


def test_key2_asks_and_resets_everything():
    app = ui.WalletApp()
    press(app, ui.PRESS)
    enter_rolls(app, "123")
    press(app, ui.KEY2)
    assert app.confirm_reset_open
    app.render()
    press(app, ui.PRESS)  # por defecto «No»
    assert not app.confirm_reset_open and app.rolls_count == 3
    press(app, ui.KEY2, ui.RIGHT, ui.PRESS)
    assert app.screen == ui.WELCOME and app.rolls_count == 0 and app.words == 24


def test_key2_from_qr_drops_account():
    app = ui.WalletApp()
    walk_to_qr(app)
    press(app, ui.KEY2, ui.LEFT, ui.PRESS)
    assert app.screen == ui.WELCOME
    assert app.account is None and app.qr_payload == "" and not app.has_phrase


# --- nada se escribe, nada se imprime ---------------------------------------


def _tree_snapshot():
    snapshot = {}
    for path in ROOT.rglob("*"):
        parts = set(path.relative_to(ROOT).parts)
        if parts & {".git", ".venv", "__pycache__", ".pytest_cache"}:
            continue
        if path.is_file():
            stat = path.stat()
            snapshot[str(path)] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def test_walk_writes_no_files_and_prints_nothing(monkeypatch, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    before = _tree_snapshot()
    real_open = builtins.open
    real_os_open = os.open

    def guarded_open(file, mode="r", *args, **kwargs):
        if any(flag in mode for flag in "wax+"):
            raise AssertionError("La interfaz intentó escribir un fichero")
        return real_open(file, mode, *args, **kwargs)

    def guarded_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND):
            raise AssertionError("La interfaz intentó escribir un fichero")
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)

    app = ui.WalletApp()
    mnemonic = walk_to_qr(app)
    press(app, ui.KEY1)
    app.render()
    press(app, ui.PRESS)
    app.render()
    press(app, ui.PRESS)
    app.render()
    press(app, ui.KEY2, ui.RIGHT, ui.PRESS)
    app.render()

    monkeypatch.undo()
    assert _tree_snapshot() == before
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""
    assert caplog.records == []
    del mnemonic


# --- reglas sobre el código -------------------------------------------------

WALLET_SOURCES = [
    ROOT / "coldwallet" / "ui" / "app.py",
    ROOT / "coldwallet" / "ui" / "drawing.py",
    ROOT / "coldwallet" / "ui" / "__init__.py",
    ROOT / "coldwallet" / "hw.py",
    ROOT / "sim.py",
    ROOT / "main.py",
]


@pytest.mark.parametrize("path", WALLET_SOURCES, ids=lambda p: p.name)
def test_no_network_random_or_logging_imports(path):
    source = path.read_text(encoding="utf-8")
    forbidden = r"^\s*(import|from)\s+(socket|requests|urllib|http|ssl|random|logging)\b"
    assert not re.search(forbidden, source, re.MULTILINE)


@pytest.mark.parametrize("path", WALLET_SOURCES, ids=lambda p: p.name)
def test_no_print_calls(path):
    source = path.read_text(encoding="utf-8")
    assert not re.search(r"(?<![\w.])print\(", source)


# --- controlador de la Raspberry (lo que se puede probar sin la placa) -------


def test_rgb565_conversion_matches_formula():
    from PIL import Image

    from coldwallet import hw

    colors = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0), (0, 0, 255),
              (18, 200, 77), (255, 210, 63), (8, 11, 16)]
    image = Image.new("RGB", (len(colors), 1))
    image.putdata(colors)
    data = hw.to_rgb565(image)
    assert len(data) == 2 * len(colors)
    for i, (r, g, b) in enumerate(colors):
        value = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        assert data[2 * i : 2 * i + 2] == value.to_bytes(2, "big")


def test_hw_imports_without_raspberry_libraries():
    import sys

    from coldwallet import hw

    assert "spidev" not in sys.modules and "gpiozero" not in sys.modules
    assert hw.BUTTON_PINS == {
        ui.UP: 6, ui.DOWN: 19, ui.LEFT: 5, ui.RIGHT: 26, ui.PRESS: 13,
        ui.KEY1: 21, ui.KEY2: 20, ui.KEY3: 16,
    }
    assert (hw.PIN_DC, hw.PIN_RST, hw.PIN_BL) == (25, 27, 24)
