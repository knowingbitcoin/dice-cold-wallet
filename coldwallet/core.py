"""Núcleo de la cartera: de las tiradas de dado a la clave pública de la cuenta.

Reglas de seguridad de este módulo:
- Nada de lo secreto (tiradas, entropía, frase, semilla, frase de contraseña)
  se escribe en disco, en registros ni en la consola.
- Los mensajes de error nunca incluyen las tiradas ni las palabras.
- La única fuente de entropía de la semilla son las tiradas. El azar no
  secreto (examen de palabras) sale del módulo secrets, nunca de random.
- Sin red: este módulo no importa nada que hable con internet.
"""

from __future__ import annotations

import hashlib
import secrets
import unicodedata
from dataclasses import dataclass

from embit import bip32, bip39, script
from embit.descriptor.checksum import add_checksum
from embit.networks import NETWORKS

# Número de tiradas necesarias para cada longitud de frase.
# Es el mismo criterio que SeedSigner y Coldcard.
ROLLS_FOR_WORDS = {12: 50, 24: 99}

# Ruta BIP84 (SegWit nativo, direcciones bc1q) de la primera cuenta de Bitcoin.
ACCOUNT_PATH = "m/84'/0'/0'"
_ACCOUNT_PATH_DESCRIPTOR = "84h/0h/0h"

_MAINNET = NETWORKS["main"]
_VALID_DIE_FACES = frozenset("123456")


@dataclass(frozen=True)
class AccountInfo:
    """Datos públicos de la cuenta. Nada de aquí permite gastar."""

    fingerprint: str  # huella de la clave maestra, 8 caracteres hexadecimales
    path: str  # ruta de derivación de la cuenta
    xpub: str  # clave pública extendida en formato xpub estándar
    zpub: str  # la misma clave en formato zpub (SLIP-132)
    descriptor: str  # descriptor de cobro con su suma de control
    descriptor_change: str  # descriptor de cambio con su suma de control


def validate_rolls(rolls: str, words: int) -> None:
    """Comprueba que las tiradas son válidas para la longitud pedida.

    Lanza ValueError con un mensaje en castellano que nunca incluye las tiradas.
    """
    if words not in ROLLS_FOR_WORDS:
        raise ValueError("La frase solo puede tener 12 o 24 palabras.")
    if not isinstance(rolls, str):
        raise ValueError("Las tiradas tienen que ser texto.")
    expected = ROLLS_FOR_WORDS[words]
    if len(rolls) != expected:
        raise ValueError(
            f"Hacen falta exactamente {expected} tiradas para {words} palabras "
            f"y hay {len(rolls)}."
        )
    if not all(ch in _VALID_DIE_FACES for ch in rolls):
        raise ValueError("Cada tirada tiene que ser un número del 1 al 6.")


def entropy_from_rolls(rolls: str, words: int) -> bytes:
    """Convierte las tiradas en entropía, igual que SeedSigner y Coldcard.

    Se calcula el SHA-256 del texto de las tiradas. Para 12 palabras se usan
    solo los primeros 16 bytes; para 24, los 32.
    """
    validate_rolls(rolls, words)
    digest = hashlib.sha256(rolls.encode("ascii")).digest()
    if words == 12:
        return digest[:16]
    return digest


def mnemonic_from_rolls(rolls: str, words: int) -> list[str]:
    """Devuelve la frase BIP39 (lista de palabras en inglés) de las tiradas."""
    entropy = entropy_from_rolls(rolls, words)
    return bip39.mnemonic_from_bytes(entropy).split()


def _mnemonic_text(mnemonic: list[str]) -> str:
    """Une y valida la frase sin dejar ninguna palabra en el mensaje de error."""
    if isinstance(mnemonic, str):
        words = mnemonic.split()
    else:
        words = list(mnemonic)
    if len(words) not in ROLLS_FOR_WORDS:
        raise ValueError("La frase tiene que tener 12 o 24 palabras.")
    text = " ".join(words)
    if not bip39.mnemonic_is_valid(text):
        raise ValueError(
            "La frase no es válida: alguna palabra no está en la lista "
            "o la última palabra no cuadra."
        )
    return text


def derive_account(mnemonic: list[str], passphrase: str = "") -> AccountInfo:
    """Calcula los datos públicos de la cuenta BIP84 a partir de la frase."""
    text = _mnemonic_text(mnemonic)
    # BIP39 pide normalizar la frase de contraseña en NFKD.
    normalized_passphrase = unicodedata.normalize("NFKD", passphrase)
    seed = bip39.mnemonic_to_seed(text, normalized_passphrase)
    root = bip32.HDKey.from_seed(seed)
    fingerprint = root.my_fingerprint.hex()
    account = root.derive(ACCOUNT_PATH).to_public()
    del root, seed

    xpub = account.to_base58(version=_MAINNET["xpub"])
    zpub = account.to_base58(version=_MAINNET["zpub"])
    origin = f"[{fingerprint}/{_ACCOUNT_PATH_DESCRIPTOR}]{xpub}"
    return AccountInfo(
        fingerprint=fingerprint,
        path=ACCOUNT_PATH,
        xpub=xpub,
        zpub=zpub,
        descriptor=add_checksum(f"wpkh({origin}/0/*)"),
        descriptor_change=add_checksum(f"wpkh({origin}/1/*)"),
    )


def receive_addresses(info: AccountInfo, count: int = 3, start: int = 0) -> list[str]:
    """Primeras direcciones de cobro (bc1q...), calculadas solo con la clave pública."""
    if count < 0 or start < 0:
        raise ValueError("El número de direcciones y el inicio no pueden ser negativos.")
    account = bip32.HDKey.from_string(info.xpub)
    receive_branch = account.derive([0])
    return [
        script.p2wpkh(receive_branch.derive([index])).address(_MAINNET)
        for index in range(start, start + count)
    ]


def quiz_positions(n_words: int, count: int = 3) -> list[int]:
    """Elige al azar qué palabras se preguntan en el examen (posiciones desde 1)."""
    if count < 1 or count > n_words:
        raise ValueError("No se pueden preguntar tantas palabras.")
    rng = secrets.SystemRandom()
    return sorted(rng.sample(range(1, n_words + 1), count))


def quiz_options(mnemonic: list[str], position: int, count: int = 4) -> list[str]:
    """Opciones para una pregunta del examen: la palabra correcta y señuelos.

    Los señuelos salen de la lista BIP39 y no repiten ninguna palabra de la
    frase, para que no haya dos respuestas que parezcan correctas.
    """
    words = list(mnemonic)
    if not 1 <= position <= len(words):
        raise ValueError("Esa posición no existe en la frase.")
    if count < 2:
        raise ValueError("Hacen falta al menos dos opciones.")
    correct = words[position - 1]
    in_phrase = set(words)
    options = [correct]
    while len(options) < count:
        candidate = secrets.choice(bip39.WORDLIST)
        if candidate not in in_phrase and candidate not in options:
            options.append(candidate)
    secrets.SystemRandom().shuffle(options)
    return options
