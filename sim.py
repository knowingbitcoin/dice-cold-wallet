"""Simulador de la cartera en el Mac (Tkinter), con la pantalla al doble de tamaño.

Teclas: flechas = joystick · Intro = pulsar el joystick · 1, 2, 3 = KEY1, KEY2, KEY3.
Idioma de la pantalla: python sim.py --lang en|es|pt (por defecto, es).

Es solo para desarrollar y probar con tiradas de PRUEBA. Nada se guarda y nada
se escribe en la consola. No lo uses nunca para generar una semilla real: un
ordenador con red no es una cartera fría.
"""

from __future__ import annotations

import argparse
import tkinter as tk
import traceback

from PIL import Image, ImageDraw, ImageTk

from coldwallet.ui.app import (
    DOWN,
    KEY1,
    KEY2,
    KEY3,
    LEFT,
    PRESS,
    RIGHT,
    UP,
    RepeatGuard,
    WalletApp,
)
from coldwallet.ui import drawing as d
from coldwallet.ui import i18n

SCALE = 2
BANNER = 36
BANNER_TEXT = i18n.t("sim.banner")

KEYMAP = {
    "Up": UP,
    "Down": DOWN,
    "Left": LEFT,
    "Right": RIGHT,
    "Return": PRESS,
    "KP_Enter": PRESS,
    "1": KEY1,
    "2": KEY2,
    "3": KEY3,
}


def with_banner(frame: Image.Image, lang: str = i18n.DEFAULT_LANGUAGE) -> Image.Image:
    """Añade encima una franja roja fija: el simulador no es una cartera fría."""
    text = i18n.t("sim.banner", lang)
    out = Image.new("RGB", (frame.width, frame.height + BANNER), (200, 0, 0))
    out.paste(frame, (0, BANNER))
    draw = ImageDraw.Draw(out)
    size = d.fit_size(text, 18, frame.width - 12)
    d.draw_text(draw, (out.width / 2, BANNER / 2), text, size, (255, 255, 255), anchor="mm")
    return out


class Simulator:
    def __init__(self, lang: str = i18n.DEFAULT_LANGUAGE) -> None:
        self.lang = i18n.check_language(lang)
        self.app = WalletApp(self.lang)
        self._guard = RepeatGuard()
        self.root = tk.Tk()
        self.root.title(i18n.t("sim.title", self.lang))
        self.root.resizable(False, False)
        # Si algo falla, se enseña una pantalla genérica y no se imprime nada:
        # el detalle del error podría contener datos secretos.
        self.root.report_callback_exception = self._on_error
        self.label = tk.Label(self.root, borderwidth=0, highlightthickness=0)
        self.label.pack()
        self._photo = None
        self.root.bind("<Key>", self._on_key)
        self._show()

    def _show(self, image: Image.Image | None = None) -> None:
        frame = image if image is not None else self.app.render()
        big = with_banner(
            frame.resize((frame.width * SCALE, frame.height * SCALE), Image.NEAREST), self.lang
        )
        # Se sustituye la imagen anterior: no se conserva ninguna pantalla vieja.
        self._photo = ImageTk.PhotoImage(big)
        self.label.configure(image=self._photo)

    def _on_key(self, event: tk.Event) -> None:
        name = event.keysym if event.keysym in KEYMAP else event.char
        action = KEYMAP.get(name)
        if action is None or not self._guard.accept(action):
            return
        self.app.handle(action)
        self._show()
        if self.app.has_pending_work:
            # Primero se pinta «Calculando…» y después se hace el cálculo.
            self.root.after(30, self._run_pending)

    def _run_pending(self) -> None:
        self.app.run_pending_work()
        self._show()

    def _on_error(self, _exc_type, exc, tb) -> None:
        # La traza mantiene vivas las variables de cada función: se vacían.
        traceback.clear_frames(tb)
        del exc, tb
        self.app.reset()
        self._show(WalletApp.render_error(self.lang))

    def run(self) -> None:
        self.root.mainloop()
        self.app.reset()


def run(lang: str = i18n.DEFAULT_LANGUAGE) -> None:
    Simulator(lang).run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulador de la cartera (solo pruebas).")
    parser.add_argument("--lang", choices=i18n.LANGUAGES, default=i18n.DEFAULT_LANGUAGE)
    run(parser.parse_args().lang)
