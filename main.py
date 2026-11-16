"""Punto de entrada: en la Raspberry arranca la pantalla real; en el Mac, el simulador.

Uso: python main.py [--sim | --hw] [--lang en|es|pt]

--lang elige el idioma de la pantalla. Por defecto es español (es), así que el
servicio de systemd, que no lo pasa, sigue igual que antes. Da igual escribirlo
en mayúsculas o minúsculas, y pt-BR, pt_br o br son el portugués de Brasil. Con
un idioma desconocido, el simulador se para con un error y el aparato sale en
español: si se parase, la pantalla se quedaría en negro y sin ningún aviso.
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
        "--lang", default=i18n.DEFAULT_LANGUAGE, metavar="{en,es,pt}",
        help="idioma de la pantalla (por defecto, es); también vale EN, pt-BR, pt_br o br",
    )
    # Como antes, cualquier otro argumento se ignora.
    args, _unknown = parser.parse_known_args(argv)
    args.use_hw = args.hw or (not args.sim and on_raspberry_pi())
    lang = i18n.normalise_language(args.lang)
    if lang is None:
        if not args.use_hw:
            parser.error(f"argument --lang: unknown language {args.lang!r} (use en, es or pt)")
        # En el aparato no se para: el servicio no enseña los errores ni se
        # reinicia, así que la pantalla se quedaría en negro. Sale en español.
        lang = i18n.DEFAULT_LANGUAGE
    args.lang = lang
    return args


def main(argv: list[str]) -> None:
    args = parse_args(argv)
    if args.use_hw:
        from coldwallet import hw

        hw.run(args.lang)
    else:
        import sim

        sim.run(args.lang)


if __name__ == "__main__":
    main(sys.argv[1:])
