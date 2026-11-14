"""Punto de entrada: en la Raspberry arranca la pantalla real; en el Mac, el simulador.

Uso: python main.py [--sim | --hw]
"""

from __future__ import annotations

import pathlib
import sys


def on_raspberry_pi() -> bool:
    model = pathlib.Path("/proc/device-tree/model")
    try:
        return "Raspberry Pi" in model.read_text(errors="ignore")
    except OSError:
        return False


def main(argv: list[str]) -> None:
    if "--hw" in argv or ("--sim" not in argv and on_raspberry_pi()):
        from coldwallet import hw

        hw.run()
    else:
        import sim

        sim.run()


if __name__ == "__main__":
    main(sys.argv[1:])
