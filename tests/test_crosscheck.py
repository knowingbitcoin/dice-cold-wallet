"""Contraste entre coldwallet.core y la implementación independiente.

Las tiradas aleatorias de este fichero son desechables y no se muestran
nunca: si un caso falla, el mensaje dice solo su número y qué campo no
coincide. Las tiradas fijas son de PRUEBA (SEMILLA DE PRUEBA — NO USAR).
"""

import ast
import hashlib
import pathlib
import secrets

import pytest

from coldwallet import core
from crosscheck import independent as ind

TEST_ROLLS_24 = "123456" * 16 + "123"  # SEMILLA DE PRUEBA — NO USAR
TEST_ROLLS_12 = TEST_ROLLS_24[:50]  # SEMILLA DE PRUEBA — NO USAR

ABANDON = ("abandon " * 11 + "about").split()


def _fail(msg: str) -> None:
    # pytrace=False: pytest no enseña código, variables ni valores.
    pytest.fail(msg, pytrace=False)


# ---------------------------------------------------------------------------
# La implementación independiente no depende de embit ni de coldwallet.
# ---------------------------------------------------------------------------

def test_independent_only_uses_stdlib():
    src = pathlib.Path(ind.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "hashlib", "hmac", "pathlib", "unicodedata"}


def test_wordlist_is_official():
    raw = (pathlib.Path(ind.__file__).parent / "english.txt").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == ind.WORDLIST_SHA256
    assert len(ind.WORDLIST) == 2048
    assert ind.WORDLIST[0] == "abandon" and ind.WORDLIST[-1] == "zoo"


# ---------------------------------------------------------------------------
# Piezas sueltas contra vectores publicados.
# ---------------------------------------------------------------------------

RIPEMD_VECTORS = [
    (b"", "9c1185a5c5e9fc54612808977ee8f548b2258d31"),
    (b"a", "0bdc9d2d256b3ee9daae347be6f4dc835a467ffe"),
    (b"abc", "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc"),
    (b"abcdefghijklmnopqrstuvwxyz", "f71c27109c692c1b56bbdceb5b9d2865b3708dbc"),
    (b"1234567890" * 8, "9b752e45573d4b39f4dbd3323cab82bf63326bfb"),
]


@pytest.mark.parametrize("msg,digest", RIPEMD_VECTORS)
def test_ripemd160_vectors(msg, digest):
    assert ind.ripemd160(msg).hex() == digest


def test_ripemd160_matches_openssl_when_available():
    try:
        ref = hashlib.new("ripemd160")
    except ValueError:
        pytest.skip("OpenSSL no ofrece RIPEMD-160 en este equipo.")
    for n in (0, 1, 55, 56, 63, 64, 65, 119, 120, 200):
        data = bytes(range(256))[:n] if n <= 256 else b""
        r = hashlib.new("ripemd160")
        r.update(data)
        assert ind.ripemd160(data) == r.digest()


def test_generator_is_on_curve_and_has_order_n():
    assert ind._is_on_curve(ind.G)
    assert ind.point_mul(ind.N - 1) == (ind.GX, (-ind.GY) % ind.P)
    assert ind.point_add(ind.point_mul(ind.N - 1), ind.G) is None
    # 2G y 3G conocidos (SEC 2 / tablas públicas de secp256k1).
    assert ind.point_mul(2)[0] == 0xC6047F9441ED7D6D3045406E95C07CD85C778E4B8CEF3CA7ABAC09B95C709EE5
    assert ind.point_mul(3)[0] == 0xF9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9


def test_pbkdf2_matches_hashlib():
    for pw, salt, it in [(b"password", b"salt", 1), (b"password", b"salt", 2048), (b"", b"mnemonic", 5)]:
        assert ind.pbkdf2_hmac_sha512(pw, salt, it) == hashlib.pbkdf2_hmac("sha512", pw, salt, it)


def test_trezor_vector_with_passphrase():
    entropy = bytes(16)
    words = ind.mnemonic_from_entropy(entropy)
    assert words == ABANDON
    seed = ind.mnemonic_to_seed(words, "TREZOR")
    assert seed.hex() == (
        "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04"
    )
    words24 = ind.mnemonic_from_entropy(bytes.fromhex("ff" * 32))
    assert " ".join(words24) == "zoo " * 23 + "vote"


def test_bip32_test_vector_1():
    # BIP32, vector de prueba 1: semilla 000102...0f, cadena m/0H.
    seed = bytes(range(16))
    k, c = ind.master_key(seed)
    master_pub = ind.point_mul(k)
    assert ind.serialize_pub(ind.XPUB_VERSION, 0, bytes(4), 0, c, master_pub) == (
        "xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8"
    )
    k1, c1 = ind.ckd_priv(k, c, ind.HARDENED)
    fp = ind.hash160(ind.ser_p(master_pub))[:4]
    assert ind.serialize_pub(ind.XPUB_VERSION, 1, fp, ind.HARDENED, c1, ind.point_mul(k1)) == (
        "xpub68Gmy5EdvgibQVfPdqkBBCHxA5htiqg55crXYuXoQRKfDBFA1WEjWgP6LHhwBZeNK1VTsfTFUHCdrfp1bgwQ9xv5ski8PX9rL2dZXvgGDnw"
    )
    # Derivación normal pública = privada (m/0H/1).
    k2, c2 = ind.ckd_priv(k1, c1, 1)
    p2, cc2 = ind.ckd_pub(ind.point_mul(k1), c1, 1)
    assert ind.point_mul(k2) == p2 and c2 == cc2


def test_bech32_reference_address():
    # BIP173: P2WPKH de la clave pública del generador G.
    program = ind.hash160(ind.ser_p(ind.G))
    assert ind.segwit_v0_address(program) == "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"


def test_descriptor_checksum_reference():
    # Ejemplo de doc/descriptors.md de Bitcoin Core.
    desc = (
        "pkh([d34db33f/44'/0'/0']xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL/1/*)"
    )
    assert ind.descriptor_checksum(desc) == "ml40v0wf"


# ---------------------------------------------------------------------------
# (a) Vectores BIP84 con la implementación independiente.
# ---------------------------------------------------------------------------

BIP84_ZPUB = "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqtfSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
BIP84_XPUB = "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V"


def test_bip84_vectors_independent():
    acc = ind.derive_account(ABANDON)
    assert acc["fingerprint"] == "73c5da0a"
    assert acc["zpub"] == BIP84_ZPUB
    assert acc["xpub"] == BIP84_XPUB
    assert acc["path"] == "m/84'/0'/0'"
    assert ind.addresses_from_xpub(acc["xpub"], 0, 2) == [
        "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
        "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g",
    ]
    assert ind.addresses_from_xpub(acc["xpub"], 1, 1) == [
        "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el",
    ]


def test_bip84_vectors_both_agree():
    acc = ind.derive_account(ABANDON)
    info = core.derive_account(ABANDON)
    assert info.descriptor == acc["descriptor"]
    assert info.descriptor_change == acc["descriptor_change"]


# ---------------------------------------------------------------------------
# (b) y (c) Contraste con tiradas aleatorias.
# ---------------------------------------------------------------------------

def _random_rolls(n: int) -> str:
    # Se repite si sale una tirada que la cartera rechazaría (pasa pocas veces).
    while True:
        rolls = "".join(secrets.choice("123456") for _ in range(n))
        if core.rolls_quality_problem(rolls) is None:
            return rolls


# Letras de la frase de contraseña: ASCII, acentos, ñ, euro, ligadura "ﬁ"
# (NFKD la convierte en "fi") y una «e» con tilde combinante.
_PASS_ALPHABET = list("abcXYZ019 -_!ñÑáéíóúü€ﬁ") + ["é"]


def _random_passphrase() -> str:
    length = 1 + secrets.randbelow(24)
    return "".join(secrets.choice(_PASS_ALPHABET) for _ in range(length))


def _mismatch(rolls: str, words: int, passphrase: str) -> str | None:
    """Devuelve qué no coincide, o None si todo coincide."""
    m_core = core.mnemonic_from_rolls(rolls, words)
    m_ind = ind.mnemonic_from_rolls(rolls, words)
    if m_core != m_ind:
        return "la frase no coincide"
    info = core.derive_account(m_core, passphrase)
    acc = ind.derive_account(m_ind, passphrase)
    for field in ("fingerprint", "path", "xpub", "zpub", "descriptor", "descriptor_change",
                  "descriptor_multipath"):
        if getattr(info, field) != acc[field]:
            return f"el campo {field} no coincide"
    if core.receive_addresses(info, 3) != ind.addresses_from_xpub(acc["xpub"], 0, 3):
        return "las direcciones de cobro no coinciden"
    first = core.receive_addresses(info, 1)[0]
    if not core.independent_account_matches(m_core, info, first, passphrase):
        return "la comprobación del aparato no coincide"
    return None


def _compare(case: int, rolls: str, words: int, passphrase: str) -> None:
    # El fallo se lanza FUERA del except: si se lanzara dentro, pytest
    # enseñaría la excepción original encadenada, con su mensaje.
    problem = None
    try:
        problem = _mismatch(rolls, words, passphrase)
    except Exception as exc:  # sin el mensaje: podría llevar algo secreto
        problem = f"excepción {type(exc).__name__}"
    if problem:
        _fail(f"Caso {case}: {problem}.")


@pytest.mark.parametrize("case", range(200), ids=lambda i: f"caso-{i}")
def test_random_rolls_match(case):
    words = 12 if case % 2 == 0 else 24
    rolls = _random_rolls(core.ROLLS_FOR_WORDS[words])
    _compare(case, rolls, words, "")


@pytest.mark.parametrize("case", range(20), ids=lambda i: f"contrasena-{i}")
def test_random_rolls_with_passphrase_match(case):
    words = 12 if case % 2 == 0 else 24
    rolls = _random_rolls(core.ROLLS_FOR_WORDS[words])
    _compare(case, rolls, words, _random_passphrase())


@pytest.mark.parametrize("words,rolls", [(24, TEST_ROLLS_24), (12, TEST_ROLLS_12)], ids=["prueba-24", "prueba-12"])
def test_fixed_test_rolls_match(words, rolls):
    assert len(TEST_ROLLS_24) == 99 and len(TEST_ROLLS_12) == 50
    _compare(-1, rolls, words, "")
