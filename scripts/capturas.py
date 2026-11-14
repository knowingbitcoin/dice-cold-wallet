"""Capturas de documentación de todas las pantallas, con las tiradas de PRUEBA fijas.

Recorre la aplicación con eventos simulados y guarda un PNG por pantalla en
docs/capturas/, cada uno con una franja roja «SEMILLA DE PRUEBA — NO USAR».

Este es el ÚNICO programa del proyecto que escribe imágenes en disco, y solo
lo hace con las tiradas de prueba de abajo, que son públicas. Nunca lo adaptes
para capturar una semilla real.

Uso: .venv/bin/python scripts/capturas.py
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from coldwallet import core  # noqa: E402
from coldwallet.ui import app as ui  # noqa: E402
from coldwallet.ui import drawing as d  # noqa: E402

# Tiradas de PRUEBA, públicas. 99 para 24 palabras; las 50 primeras para 12.
TEST_ROLLS_24 = "123456" * 16 + "123"
TEST_ROLLS_12 = TEST_ROLLS_24[:50]
assert len(TEST_ROLLS_24) == 99 and len(TEST_ROLLS_12) == 50

OUT_DIR = ROOT / "docs" / "capturas"
SCALE = 2
BAND = 40
BAND_TEXT = "SEMILLA DE PRUEBA — NO USAR"


def press(app: ui.WalletApp, *events: str) -> None:
    for event in events:
        app.handle(event)


def enter_roll(app: ui.WalletApp, face: int) -> None:
    press(app, *ui.moves_to_face(app.cursor_face, face), ui.PRESS)


def save(app: ui.WalletApp, name: str) -> None:
    frame = app.render().resize((d.WIDTH * SCALE, d.HEIGHT * SCALE), Image.NEAREST)
    out = Image.new("RGB", (frame.width, frame.height + BAND), (200, 0, 0))
    out.paste(frame, (0, BAND))
    draw = ImageDraw.Draw(out)
    d.draw_text(draw, (out.width / 2, BAND / 2), BAND_TEXT, 22, (255, 255, 255), bold=True, anchor="mm")
    out.save(OUT_DIR / f"{name}.png")


def answer_exam(app: ui.WalletApp, mnemonic: list[str], wrong: bool = False) -> None:
    correct = mnemonic[app.exam_position - 1]
    options = app.exam_options
    target = next(i for i, w in enumerate(options) if (w != correct) == wrong)
    while app.exam_choice != target:
        press(app, ui.DOWN)
    press(app, ui.PRESS)


def run() -> list[str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.png"):
        old.unlink()

    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    app = ui.WalletApp()
    save(app, "01-bienvenida")

    press(app, ui.PRESS)
    save(app, "02-tiradas-vacio")
    for roll in TEST_ROLLS_24[:37]:
        enter_roll(app, int(roll))
    save(app, "03-tiradas-37")

    press(app, ui.KEY2)
    save(app, "04-empezar-de-nuevo")
    press(app, ui.KEY2)  # cancela

    for roll in TEST_ROLLS_24[37:]:
        enter_roll(app, int(roll))
    save(app, "05-confirmar-tiradas")
    press(app, ui.UP, ui.PRESS)

    save(app, "06-aviso")
    press(app, ui.PRESS)
    save(app, "07-frase-1-a-4")
    press(app, *[ui.RIGHT] * 5)
    save(app, "08-frase-21-a-24")
    press(app, ui.PRESS)

    save(app, "09-examen")
    answer_exam(app, mnemonic, wrong=True)
    save(app, "10-examen-fallado")
    press(app, ui.PRESS)
    while app.screen == ui.PHRASE:
        press(app, ui.RIGHT)
    for _ in range(ui.EXAM_QUESTIONS):
        answer_exam(app, mnemonic)
    save(app, "11-examen-aprobado")

    press(app, ui.PRESS)
    save(app, "12-calculando")
    app.run_pending_work()
    save(app, "13-qr-zpub")
    press(app, ui.KEY1)
    save(app, "14-qr-descriptor")
    press(app, ui.PRESS)
    save(app, "15-comprobacion")
    press(app, ui.PRESS)
    save(app, "16-fin")

    # Variante de 12 palabras: bienvenida y confirmación con 50 tiradas.
    app = ui.WalletApp()
    press(app, ui.LEFT)
    save(app, "17-bienvenida-12")
    press(app, ui.PRESS)
    for roll in TEST_ROLLS_12:
        enter_roll(app, int(roll))
    save(app, "18-confirmar-tiradas-12")

    return sorted(p.name for p in OUT_DIR.glob("*.png"))


if __name__ == "__main__":
    for name in run():
        print(name)  # solo nombres de fichero: no hay nada secreto
