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


def save(app_or_image, name: str) -> None:
    frame = app_or_image.render() if isinstance(app_or_image, ui.WalletApp) else app_or_image
    frame = frame.resize((d.WIDTH * SCALE, d.HEIGHT * SCALE), Image.NEAREST)
    out = Image.new("RGB", (frame.width, frame.height + BAND), (200, 0, 0))
    out.paste(frame, (0, BAND))
    draw = ImageDraw.Draw(out)
    d.draw_text(draw, (out.width / 2, BAND / 2), BAND_TEXT, 22, (255, 255, 255), bold=True, anchor="mm")
    out.save(OUT_DIR / f"{name}.png")


def fixed_quiz_options(mnemonic: list[str], position: int, count: int = 4) -> list[str]:
    """Opciones fijas SOLO para las capturas, para que salgan iguales cada vez.

    La cartera de verdad las elige al azar con secrets (core.quiz_options).
    """
    words = list(mnemonic)
    correct = words[position - 1]
    others = [w for w in dict.fromkeys(words) if w != correct][: count - 1]
    return [others[0], correct] + others[1:]


def answer_exam(app: ui.WalletApp, mnemonic: list[str], wrong: bool = False) -> None:
    correct = mnemonic[app.exam_position - 1]
    options = app.exam_options
    target = next(i for i, w in enumerate(options) if (w != correct) == wrong)
    while app.exam_choice != target:
        press(app, ui.DOWN)
    press(app, ui.PRESS)


def enter_all(app: ui.WalletApp, rolls: str) -> None:
    for roll in rolls:
        enter_roll(app, int(roll))


def run() -> list[str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.png"):
        old.unlink()
    core.quiz_options = fixed_quiz_options  # solo en este programa de capturas

    mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
    app = ui.WalletApp()
    save(app, "01-bienvenida")

    press(app, ui.PRESS)
    save(app, "02-tiradas-vacio")
    enter_all(app, TEST_ROLLS_24[:37])
    save(app, "03-tiradas-37")

    press(app, ui.KEY2)
    save(app, "04-empezar-de-nuevo")
    press(app, ui.KEY2)  # cancela

    enter_all(app, TEST_ROLLS_24[37:])
    save(app, "05-revisar-tiradas")
    press(app, *[ui.DOWN] * 2, ui.RIGHT, ui.PRESS)
    save(app, "06-cambiar-una-tirada")
    press(app, ui.KEY3)  # deshace el cambio
    press(app, *[ui.DOWN] * 15)
    save(app, "07-revisar-tiradas-ultima-pagina")
    press(app, ui.KEY1)
    save(app, "08-confirmar-tiradas")
    press(app, ui.LEFT, ui.PRESS)

    save(app, "09-aviso")
    press(app, ui.PRESS)
    save(app, "10-frase-1-a-4")
    press(app, *[ui.RIGHT] * 5)
    save(app, "11-frase-21-a-24")
    press(app, ui.PRESS)

    save(app, "12-examen")
    answer_exam(app, mnemonic)
    answer_exam(app, mnemonic, wrong=True)
    save(app, "13-examen-fallado")
    press(app, ui.PRESS)
    save(app, "14-frase-corregir")
    press(app, ui.PRESS)
    while app.screen == ui.EXAM:
        answer_exam(app, mnemonic)
    save(app, "15-examen-aprobado")

    press(app, ui.DOWN, ui.PRESS)
    save(app, "16-calculando")
    app.run_pending_work()
    save(app, "17-qr-zpub")
    press(app, ui.KEY1)
    save(app, "18-qr-descriptor")
    press(app, ui.PRESS)
    save(app, "19-comprobacion")
    press(app, ui.PRESS)
    save(app, "20-fin")

    # Variante de 12 palabras: bienvenida y revisión con 50 tiradas.
    app = ui.WalletApp()
    press(app, ui.LEFT)
    save(app, "21-bienvenida-12")
    press(app, ui.PRESS)
    enter_all(app, TEST_ROLLS_12)
    save(app, "22-revisar-tiradas-12")

    # Tiradas que no parecen al azar: las de prueba con las 8 primeras cambiadas a 1.
    app = ui.WalletApp()
    press(app, ui.PRESS)
    enter_all(app, TEST_ROLLS_24)
    for index in range(8):
        while app.review_index < index:
            press(app, ui.RIGHT)
        press(app, ui.PRESS)
        while app._rolls[index] != "1":  # noqa: SLF001 (solo capturas)
            press(app, ui.UP)
        press(app, ui.PRESS)
    press(app, ui.KEY1, ui.LEFT, ui.PRESS)
    save(app, "23-tiradas-raras")

    # Pantallas de error y de bloqueo (no llevan datos).
    save(ui.WalletApp.render_network_warning(), "24-hay-red")
    save(ui.WalletApp.render_error(), "25-algo-ha-fallado")
    app = ui.WalletApp()
    app._fail_mismatch()  # noqa: SLF001 (solo capturas)
    save(app, "26-no-coinciden")

    return sorted(p.name for p in OUT_DIR.glob("*.png"))


if __name__ == "__main__":
    for name in run():
        print(name)  # solo nombres de fichero: no hay nada secreto
