"""Punto de entrada: en la Raspberry arranca la pantalla real; en el Mac, el simulador.

Uso: python main.py [--sim | --hw] [--lang en|es|pt]

--lang elige el idioma de la pantalla. Por defecto es español (es), así que el
servicio de systemd, que no lo pasa, sigue igual que antes.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from coldwallet.ui import i18n


def on_raspberry_pi() -> bool:
    model = pathlib.Path("/proc/device-tree/model")
    try:
        return "Raspberry Pi" in model.read_text(errors="ignore")
    except OSError:
        return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cartera fría de dados.")
    parser.add_argument("--sim", action="store_true", help="simulador en el Mac")
    parser.add_argument("--hw", action="store_true", help="pantalla y botones de la Raspberry")
    parser.add_argument(
        "--lang", choices=i18n.LANGUAGES, default=i18n.DEFAULT_LANGUAGE,
        help="idioma de la pantalla (por defecto, es)",
    )
    # Como antes, cualquier otro argumento se ignora.
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    if args.hw or (not args.sim and on_raspberry_pi()):
        from coldwallet import hw

        hw.run(args.lang)
    else:
        import sim

        sim.run(args.lang)


if __name__ == "__main__":
    main(sys.argv[1:])
