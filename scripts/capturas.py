"""Capturas de documentación de todas las pantallas, con las tiradas de PRUEBA fijas.

Recorre la aplicación con eventos simulados y guarda un PNG por pantalla, cada
uno con una franja roja «SEMILLA DE PRUEBA — NO USAR» (traducida al idioma de
la captura).

Este es el ÚNICO programa del proyecto que escribe imágenes en disco, y solo
lo hace con las tiradas de prueba de abajo, que son públicas. Nunca lo adaptes
para capturar una semilla real.

Uso:
  .venv/bin/python scripts/capturas.py             # docs/capturas/ (español, nombres de siempre)
  .venv/bin/python scripts/capturas.py --lang en   # docs/screenshots/en/NN-<nombre>.png
  .venv/bin/python scripts/capturas.py --lang all  # docs/screenshots/{en,es,pt}/

En docs/screenshots/ los nombres de fichero son los mismos en los tres idiomas
(en inglés), para que un enlace sirva cambiando solo la carpeta.
"""

from __future__ import annotations

import argparse
import contextlib
import pathlib
import sys
from collections.abc import Iterator

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from coldwallet import core  # noqa: E402
from coldwallet.ui import app as ui  # noqa: E402
from coldwallet.ui import drawing as d  # noqa: E402
from coldwallet.ui import i18n  # noqa: E402

# Tiradas de PRUEBA, públicas. 99 para 24 palabras; las 50 primeras para 12.
TEST_ROLLS_24 = "123456" * 16 + "123"
TEST_ROLLS_12 = TEST_ROLLS_24[:50]
assert len(TEST_ROLLS_24) == 99 and len(TEST_ROLLS_12) == 50

OUT_DIR = ROOT / "docs" / "capturas"  # las de siempre, en español
SHOTS_DIR = ROOT / "docs" / "screenshots"  # una carpeta por idioma
SCALE = 2
BAND = 40
BAND_TEXT = i18n.t("shots.band")


def press(app: ui.WalletApp, *events: str) -> None:
    for event in events:
        app.handle(event)


def enter_roll(app: ui.WalletApp, face: int) -> None:
    press(app, *ui.moves_to_face(app.cursor_face, face), ui.PRESS)


def with_band(frame: Image.Image, lang: str = i18n.DEFAULT_LANGUAGE) -> Image.Image:
    """Pantalla al doble de tamaño con la franja roja de semilla de prueba encima."""
    text = i18n.t("shots.band", lang)
    frame = frame.resize((d.WIDTH * SCALE, d.HEIGHT * SCALE), Image.NEAREST)
    out = Image.new("RGB", (frame.width, frame.height + BAND), (200, 0, 0))
    out.paste(frame, (0, BAND))
    draw = ImageDraw.Draw(out)
    size = d.fit_size(text, 22, out.width - 16)
    d.draw_text(draw, (out.width / 2, BAND / 2), text, size, (255, 255, 255), bold=True, anchor="mm")
    return out


def fixed_quiz_options(mnemonic: list[str], position: int, count: int = 4) -> list[str]:
    """Opciones fijas SOLO para las capturas, para que salgan iguales cada vez.

    La cartera de verdad las elige al azar con secrets (core.quiz_options).
    """
    words = list(mnemonic)
    correct = words[position - 1]
    others = [w for w in dict.fromkeys(words) if w != correct][: count - 1]
    return [others[0], correct] + others[1:]


@contextlib.contextmanager
def fixed_quiz():
    """Cambia las opciones al azar del examen por las fijas mientras dura el bloque."""
    real = core.quiz_options
    core.quiz_options = fixed_quiz_options  # solo en este programa de capturas
    try:
        yield
    finally:
        core.quiz_options = real


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


Shot = tuple[str, str, Image.Image]  # (nombre en docs/capturas, nombre en docs/screenshots, imagen)


def shots(lang: str = i18n.DEFAULT_LANGUAGE) -> Iterator[Shot]:
    """Recorre la cartera y devuelve cada captura en memoria, sin escribir nada."""
    lang = i18n.check_language(lang)

    def shot(app_or_image, name_es: str, name_en: str) -> Shot:
        frame = app_or_image.render() if isinstance(app_or_image, ui.WalletApp) else app_or_image
        return name_es, name_en, with_band(frame, lang)

    with fixed_quiz():
        mnemonic = core.mnemonic_from_rolls(TEST_ROLLS_24, 24)
        app = ui.WalletApp(lang)
        yield shot(app, "01-bienvenida", "01-welcome")

        press(app, ui.PRESS)
        yield shot(app, "02-tiradas-vacio", "02-rolls-empty")
        enter_all(app, TEST_ROLLS_24[:37])
        yield shot(app, "03-tiradas-37", "03-rolls-37")

        press(app, ui.KEY2)
        yield shot(app, "04-empezar-de-nuevo", "04-start-over")
        press(app, ui.KEY2)  # cancela

        enter_all(app, TEST_ROLLS_24[37:])
        yield shot(app, "05-revisar-tiradas", "05-review-rolls")
        press(app, *[ui.DOWN] * 2, ui.RIGHT, ui.PRESS)
        yield shot(app, "06-cambiar-una-tirada", "06-change-a-roll")
        press(app, ui.KEY3)  # deshace el cambio
        press(app, *[ui.DOWN] * 15)
        yield shot(app, "07-revisar-tiradas-ultima-pagina", "07-review-rolls-last-page")
        press(app, ui.KEY1)
        yield shot(app, "08-confirmar-tiradas", "08-confirm-rolls")
        press(app, ui.LEFT, ui.PRESS)

        yield shot(app, "09-aviso", "09-warning")
        press(app, ui.PRESS)
        yield shot(app, "10-frase-1-a-4", "10-phrase-1-to-4")
        press(app, *[ui.RIGHT] * 5)
        yield shot(app, "11-frase-21-a-24", "11-phrase-21-to-24")
        press(app, ui.PRESS)

        yield shot(app, "12-examen", "12-quiz")
        answer_exam(app, mnemonic)
        answer_exam(app, mnemonic, wrong=True)
        yield shot(app, "13-examen-fallado", "13-quiz-failed")
        press(app, ui.PRESS)
        yield shot(app, "14-frase-corregir", "14-phrase-correct")
        press(app, ui.PRESS)
        while app.screen == ui.EXAM:
            answer_exam(app, mnemonic)
        yield shot(app, "15-examen-aprobado", "15-quiz-passed")

        press(app, ui.DOWN, ui.PRESS)
        yield shot(app, "16-calculando", "16-computing")
        app.run_pending_work()
        yield shot(app, "17-qr-zpub", "17-qr-zpub")
        press(app, ui.KEY1)
        yield shot(app, "18-qr-descriptor", "18-qr-descriptor")
        press(app, ui.PRESS)
        yield shot(app, "19-comprobacion", "19-check")
        press(app, ui.PRESS)
        yield shot(app, "20-fin", "20-end")

        # Variante de 12 palabras: bienvenida y revisión con 50 tiradas.
        app = ui.WalletApp(lang)
        press(app, ui.LEFT)
        yield shot(app, "21-bienvenida-12", "21-welcome-12")
        press(app, ui.PRESS)
        enter_all(app, TEST_ROLLS_12)
        yield shot(app, "22-revisar-tiradas-12", "22-review-rolls-12")

        # Tiradas que no parecen al azar: las de prueba con las 8 primeras cambiadas a 1.
        app = ui.WalletApp(lang)
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
        yield shot(app, "23-tiradas-raras", "23-rolls-not-random")

        # Pantallas de error y de bloqueo (no llevan datos).
        yield shot(ui.WalletApp.render_network_warning(lang), "24-hay-red", "24-network-found")
        yield shot(ui.WalletApp.render_error(lang), "25-algo-ha-fallado", "25-error")
        app = ui.WalletApp(lang)
        app._fail_mismatch()  # noqa: SLF001 (solo capturas)
        yield shot(app, "26-no-coinciden", "26-mismatch")


def _write(out_dir: pathlib.Path, images: list[tuple[str, Image.Image]]) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):
        old.unlink()
    for name, image in images:
        image.save(out_dir / f"{name}.png")
    return sorted(p.name for p in out_dir.glob("*.png"))


def run(lang: str | None = None) -> list[str]:
    """Sin idioma: docs/capturas/ en español, como siempre. Con idioma: docs/screenshots/<idioma>/."""
    if lang is None:
        return _write(OUT_DIR, [(name_es, image) for name_es, _, image in shots()])
    lang = i18n.check_language(lang)
    names = _write(SHOTS_DIR / lang, [(name_en, image) for _, name_en, image in shots(lang)])
    return [f"{lang}/{name}" for name in names]


def main(argv: list[str]) -> list[str]:
    parser = argparse.ArgumentParser(description="Capturas con las tiradas de PRUEBA.")
    parser.add_argument("--lang", choices=(*i18n.LANGUAGES, "all"), default=None)
    lang = parser.parse_args(argv).lang
    if lang == "all":
        return [name for code in i18n.LANGUAGES for name in run(code)]
    return run(lang)


if __name__ == "__main__":
    for name in main(sys.argv[1:]):
        print(name)  # solo nombres de fichero: no hay nada secreto
