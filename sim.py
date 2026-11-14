"""Simulador de la cartera en el Mac (Tkinter), con la pantalla al doble de tamaño.

Teclas: flechas = joystick · Intro = pulsar el joystick · 1, 2, 3 = KEY1, KEY2, KEY3.

Es solo para desarrollar y probar con tiradas de PRUEBA. Nada se guarda y nada
se escribe en la consola. No lo uses nunca para generar una semilla real: un
ordenador con red no es una cartera fría.
"""

from __future__ import annotations

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

SCALE = 2
BANNER = 36
BANNER_TEXT = "SIMULADOR · SOLO PRUEBAS · NO USAR CON DINERO"

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


def with_banner(frame: Image.Image) -> Image.Image:
    """Añade encima una franja roja fija: el simulador no es una cartera fría."""
    out = Image.new("RGB", (frame.width, frame.height + BANNER), (200, 0, 0))
    out.paste(frame, (0, BANNER))
    draw = ImageDraw.Draw(out)
    size = d.fit_size(BANNER_TEXT, 18, frame.width - 12)
    d.draw_text(draw, (out.width / 2, BANNER / 2), BANNER_TEXT, size, (255, 255, 255), anchor="mm")
    return out


class Simulator:
    def __init__(self) -> None:
        self.app = WalletApp()
        self._guard = RepeatGuard()
        self.root = tk.Tk()
        self.root.title("Cartera fría · simulador")
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
        big = with_banner(frame.resize((frame.width * SCALE, frame.height * SCALE), Image.NEAREST))
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
        self._show(WalletApp.render_error())

    def run(self) -> None:
        self.root.mainloop()
        self.app.reset()


def run() -> None:
    Simulator().run()


if __name__ == "__main__":
    run()
