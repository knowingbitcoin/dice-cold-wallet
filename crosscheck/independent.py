"""Segunda implementación, independiente, del núcleo de la cartera.

Sirve solo para contrastar coldwallet/core.py. Está escrita desde las
especificaciones (BIP39, BIP32, BIP84, SLIP-132, BIP173, BIP-380, SEC 2 y la
descripción original de RIPEMD-160) y usa solo la biblioteca estándar de
Python. No importa embit ni nada de coldwallet.

Reglas: nada de lo secreto se imprime, se registra ni se escribe en disco.
Esta implementación es lenta y no intenta resistir ataques de canal lateral:
no se usa nunca para la cartera de verdad, solo en las pruebas.
"""

from __future__ import annotations

import hashlib
import hmac
import pathlib
import unicodedata

# ---------------------------------------------------------------------------
# Lista de palabras BIP39 (inglés), comprobada por su huella SHA-256.
# ---------------------------------------------------------------------------

WORDLIST_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
_WORDLIST_PATH = pathlib.Path(__file__).resolve().parent / "english.txt"


def _load_wordlist() -> list[str]:
    raw = _WORDLIST_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != WORDLIST_SHA256:
        raise RuntimeError("La lista de palabras BIP39 no es la oficial.")
    words = raw.decode("ascii").split("\n")
    if words and words[-1] == "":
        words.pop()
    if len(words) != 2048:
        raise RuntimeError("La lista de palabras BIP39 no tiene 2048 palabras.")
    return words


WORDLIST = _load_wordlist()

# ---------------------------------------------------------------------------
# Curva secp256k1 (SEC 2, apartado 2.4.1), en coordenadas afines.
# ---------------------------------------------------------------------------

P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
N = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G = (GX, GY)

# El punto del infinito se representa con None.


def _is_on_curve(pt) -> bool:
    if pt is None:
        return True
    x, y = pt
    return (y * y - x * x * x - 7) % P == 0


def point_add(a, b):
    """Suma de dos puntos de la curva y^2 = x^3 + 7 sobre F_p."""
    if a is None:
        return b
    if b is None:
        return a
    x1, y1 = a
    x2, y2 = b
    if x1 == x2:
        if (y1 + y2) % P == 0:
            return None  # a + (-a) = infinito
        # Duplicación: pendiente de la tangente.
        lam = (3 * x1 * x1) * pow(2 * y1, -1, P) % P
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    y3 = (lam * (x1 - x3) - y1) % P
    return (x3, y3)


def point_mul(k: int, pt=G):
    """Multiplicación escalar por el método de doblar y sumar."""
    if k % N == 0 or pt is None:
        return None
    k %= N
    result = None
    addend = pt
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


def ser_p(pt) -> bytes:
    """Punto comprimido de 33 bytes (SEC 1, 2.3.3)."""
    if pt is None:
        raise ValueError("El punto del infinito no se puede serializar.")
    x, y = pt
    return bytes([2 + (y & 1)]) + x.to_bytes(32, "big")


# ---------------------------------------------------------------------------
# RIPEMD-160 (Dobbertin, Bosselaers y Preneel, 1996) y hash160.
# Se escribe aquí porque OpenSSL 3 puede no ofrecerlo en hashlib.
# ---------------------------------------------------------------------------

_RL = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2, 14, 11, 8,
    3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12,
    1, 9, 11, 10, 0, 8, 12, 4, 13, 3, 7, 15, 14, 5, 6, 2,
    4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13,
]
_RR = [
    5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12,
    6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4, 9, 1, 2,
    15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13,
    8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2, 13, 9, 7, 10, 14,
    12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11,
]
_SL = [
    11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8,
    7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9, 11, 7, 13, 12,
    11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5,
    11, 12, 14, 15, 14, 15, 9, 8, 9, 14, 5, 6, 8, 6, 5, 12,
    9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6,
]
_SR = [
    8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6,
    9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6, 15, 13, 11,
    9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5,
    15, 5, 8, 11, 14, 14, 6, 14, 6, 9, 12, 9, 12, 5, 15, 8,
    8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11,
]
_KL = [0x00000000, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
_KR = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0x00000000]
_M32 = 0xFFFFFFFF


def _rol(x: int, n: int) -> int:
    x &= _M32
    return ((x << n) | (x >> (32 - n))) & _M32


def _f(j: int, x: int, y: int, z: int) -> int:
    if j < 16:
        return x ^ y ^ z
    if j < 32:
        return (x & y) | (~x & z)
    if j < 48:
        return (x | ~y) ^ z
    if j < 64:
        return (x & z) | (y & ~z)
    return x ^ (y | ~z)


def ripemd160(data: bytes) -> bytes:
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    msg = bytearray(data)
    bit_len = (8 * len(data)) & 0xFFFFFFFFFFFFFFFF
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "little")
    for off in range(0, len(msg), 64):
        x = [int.from_bytes(msg[off + 4 * i: off + 4 * i + 4], "little") for i in range(16)]
        al, bl, cl, dl, el = h
        ar, br, cr, dr, er = h
        for j in range(80):
            rnd = j // 16
            t = _rol(al + (_f(j, bl, cl, dl) & _M32) + x[_RL[j]] + _KL[rnd], _SL[j]) + el
            al, el, dl, cl, bl = el, dl, _rol(cl, 10), bl, t & _M32
            t = _rol(ar + (_f(79 - j, br, cr, dr) & _M32) + x[_RR[j]] + _KR[rnd], _SR[j]) + er
            ar, er, dr, cr, br = er, dr, _rol(cr, 10), br, t & _M32
        t = (h[1] + cl + dr) & _M32
        h[1] = (h[2] + dl + er) & _M32
        h[2] = (h[3] + el + ar) & _M32
        h[3] = (h[4] + al + br) & _M32
        h[4] = (h[0] + bl + cr) & _M32
        h[0] = t
    return b"".join(v.to_bytes(4, "little") for v in h)


def hash160(data: bytes) -> bytes:
    return ripemd160(hashlib.sha256(data).digest())


# ---------------------------------------------------------------------------
# Base58Check.
# ---------------------------------------------------------------------------

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def base58check(payload: bytes) -> str:
    data = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    num = int.from_bytes(data, "big")
    out = ""
    while num:
        num, rem = divmod(num, 58)
        out = _B58[rem] + out
    pad = len(data) - len(data.lstrip(b"\x00"))
    return "1" * pad + out


def base58check_decode(text: str) -> bytes:
    num = 0
    for ch in text:
        num = num * 58 + _B58.index(ch)
    pad = len(text) - len(text.lstrip("1"))
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num else b""
    data = b"\x00" * pad + body
    payload, check = data[:-4], data[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != check:
        raise ValueError("Suma de control base58 incorrecta.")
    return payload


# ---------------------------------------------------------------------------
# Bech32 versión 0 (BIP173) para direcciones bc1q.
# ---------------------------------------------------------------------------

_BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GEN = [0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3]


def _bech32_polymod(values) -> int:
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1FFFFFF) << 5) ^ v
        for i in range(5):
            if (top >> i) & 1:
                chk ^= _BECH32_GEN[i]
    return chk


def _bech32_hrp_expand(hrp: str) -> list[int]:
    return [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]


def _bech32_create_checksum(hrp: str, data: list[int]) -> list[int]:
    polymod = _bech32_polymod(_bech32_hrp_expand(hrp) + data + [0] * 6) ^ 1
    return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]


def _convertbits(data: bytes, frombits: int, tobits: int) -> list[int]:
    acc = 0
    bits = 0
    out = []
    maxv = (1 << tobits) - 1
    for value in data:
        acc = (acc << frombits) | value
        bits += frombits
        while bits >= tobits:
            bits -= tobits
            out.append((acc >> bits) & maxv)
    if bits:
        out.append((acc << (tobits - bits)) & maxv)
    return out


def segwit_v0_address(program: bytes, hrp: str = "bc") -> str:
    data = [0] + _convertbits(program, 8, 5)
    combined = data + _bech32_create_checksum(hrp, data)
    return hrp + "1" + "".join(_BECH32_CHARSET[d] for d in combined)


# ---------------------------------------------------------------------------
# Suma de control de descriptores (BIP-380).
# ---------------------------------------------------------------------------

_DESC_INPUT_CHARSET = (
    "0123456789()[],'/*abcdefgh@:$%{}"
    "IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~"
    "ijklmnopqrstuvwxyzABCDEFGH`#\"\\ "
)
_DESC_GEN = [0xF5DEE51989, 0xA9FDCA3312, 0x1BAB10E32D, 0x3706B1677A, 0x644D626FFD]


def _desc_polymod(c: int, val: int) -> int:
    c0 = c >> 35
    c = ((c & 0x7FFFFFFFF) << 5) ^ val
    for i in range(5):
        if (c0 >> i) & 1:
            c ^= _DESC_GEN[i]
    return c


def descriptor_checksum(desc: str) -> str:
    c = 1
    cls = 0
    clscount = 0
    for ch in desc:
        pos = _DESC_INPUT_CHARSET.find(ch)
        if pos == -1:
            raise ValueError("Carácter no válido en el descriptor.")
        c = _desc_polymod(c, pos & 31)
        cls = cls * 3 + (pos >> 5)
        clscount += 1
        if clscount == 3:
            c = _desc_polymod(c, cls)
            cls = 0
            clscount = 0
    if clscount > 0:
        c = _desc_polymod(c, cls)
    for _ in range(8):
        c = _desc_polymod(c, 0)
    c ^= 1
    return "".join(_BECH32_CHARSET[(c >> (5 * (7 - j))) & 31] for j in range(8))


def add_descriptor_checksum(desc: str) -> str:
    return desc + "#" + descriptor_checksum(desc)


# ---------------------------------------------------------------------------
# BIP39: tiradas → entropía → frase → semilla.
# ---------------------------------------------------------------------------

ROLLS_FOR_WORDS = {12: 50, 24: 99}


def entropy_from_rolls(rolls: str, words: int) -> bytes:
    if words not in ROLLS_FOR_WORDS or len(rolls) != ROLLS_FOR_WORDS[words]:
        raise ValueError("Número de tiradas incorrecto.")
    if any(ch not in "123456" for ch in rolls):
        raise ValueError("Tirada fuera de 1-6.")
    digest = hashlib.sha256(rolls.encode("ascii")).digest()
    return digest[:16] if words == 12 else digest


def mnemonic_from_entropy(entropy: bytes) -> list[str]:
    ent_bits = 8 * len(entropy)
    if ent_bits not in (128, 160, 192, 224, 256):
        raise ValueError("Longitud de entropía no admitida.")
    cs_bits = ent_bits // 32
    checksum = int.from_bytes(hashlib.sha256(entropy).digest(), "big") >> (256 - cs_bits)
    total = (int.from_bytes(entropy, "big") << cs_bits) | checksum
    n_words = (ent_bits + cs_bits) // 11
    return [WORDLIST[(total >> (11 * (n_words - 1 - i))) & 0x7FF] for i in range(n_words)]


def mnemonic_from_rolls(rolls: str, words: int) -> list[str]:
    return mnemonic_from_entropy(entropy_from_rolls(rolls, words))


def pbkdf2_hmac_sha512(password: bytes, salt: bytes, iterations: int, dklen: int = 64) -> bytes:
    """PBKDF2 (RFC 8018, apartado 5.2) con HMAC-SHA512, escrito a mano."""
    base = hmac.new(password, digestmod=hashlib.sha512)
    hlen = base.digest_size
    blocks = -(-dklen // hlen)
    out = b""
    for i in range(1, blocks + 1):
        mac = base.copy()
        mac.update(salt + i.to_bytes(4, "big"))
        u = mac.digest()
        acc = int.from_bytes(u, "big")
        for _ in range(iterations - 1):
            mac = base.copy()
            mac.update(u)
            u = mac.digest()
            acc ^= int.from_bytes(u, "big")
        out += acc.to_bytes(hlen, "big")
    return out[:dklen]


def mnemonic_to_seed(mnemonic: list[str], passphrase: str = "") -> bytes:
    sentence = unicodedata.normalize("NFKD", " ".join(mnemonic))
    salt = unicodedata.normalize("NFKD", "mnemonic" + passphrase)
    return pbkdf2_hmac_sha512(sentence.encode("utf-8"), salt.encode("utf-8"), 2048, 64)


# ---------------------------------------------------------------------------
# BIP32.
# ---------------------------------------------------------------------------

HARDENED = 0x80000000
XPUB_VERSION = bytes.fromhex("0488B21E")
ZPUB_VERSION = bytes.fromhex("04B24746")  # SLIP-132, P2WPKH mainnet


def master_key(seed: bytes) -> tuple[int, bytes]:
    i = hmac.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
    k = int.from_bytes(i[:32], "big")
    if k == 0 or k >= N:
        raise ValueError("Clave maestra no válida.")
    return k, i[32:]


def ckd_priv(k: int, chain: bytes, index: int) -> tuple[int, bytes]:
    """Derivación de hijo privado (endurecida o normal)."""
    if index >= HARDENED:
        data = b"\x00" + k.to_bytes(32, "big") + index.to_bytes(4, "big")
    else:
        data = ser_p(point_mul(k)) + index.to_bytes(4, "big")
    i = hmac.new(chain, data, hashlib.sha512).digest()
    il = int.from_bytes(i[:32], "big")
    child = (il + k) % N
    if il >= N or child == 0:
        raise ValueError("Índice no válido; pasa al siguiente.")
    return child, i[32:]


def ckd_pub(pt, chain: bytes, index: int):
    """Derivación de hijo público (solo normal)."""
    if index >= HARDENED:
        raise ValueError("No se puede derivar un hijo endurecido desde la clave pública.")
    i = hmac.new(chain, ser_p(pt) + index.to_bytes(4, "big"), hashlib.sha512).digest()
    il = int.from_bytes(i[:32], "big")
    if il >= N:
        raise ValueError("Índice no válido; pasa al siguiente.")
    child = point_add(point_mul(il), pt)
    if child is None:
        raise ValueError("Índice no válido; pasa al siguiente.")
    return child, i[32:]


def serialize_pub(version: bytes, depth: int, parent_fp: bytes, child: int,
                  chain: bytes, pt) -> str:
    payload = (
        version
        + bytes([depth])
        + parent_fp
        + child.to_bytes(4, "big")
        + chain
        + ser_p(pt)
    )
    assert len(payload) == 78
    return base58check(payload)


def parse_xpub(text: str):
    payload = base58check_decode(text)
    if len(payload) != 78:
        raise ValueError("Clave extendida con longitud incorrecta.")
    chain = payload[13:45]
    key = payload[45:]
    x = int.from_bytes(key[1:], "big")
    y = pow((x * x * x + 7) % P, (P + 1) // 4, P)
    if (y & 1) != (key[0] & 1):
        y = P - y
    pt = (x, y)
    if not _is_on_curve(pt):
        raise ValueError("El punto no está en la curva.")
    return pt, chain


# ---------------------------------------------------------------------------
# Cuenta BIP84 completa.
# ---------------------------------------------------------------------------

ACCOUNT_PATH = "m/84'/0'/0'"


def derive_account(mnemonic: list[str], passphrase: str = "") -> dict:
    seed = mnemonic_to_seed(mnemonic, passphrase)
    k, c = master_key(seed)
    master_fp = hash160(ser_p(point_mul(k)))[:4]

    k1, c1 = ckd_priv(k, c, 84 + HARDENED)
    k2, c2 = ckd_priv(k1, c1, 0 + HARDENED)
    parent_fp = hash160(ser_p(point_mul(k2)))[:4]
    k3, c3 = ckd_priv(k2, c2, 0 + HARDENED)
    acc_pub = point_mul(k3)

    xpub = serialize_pub(XPUB_VERSION, 3, parent_fp, HARDENED, c3, acc_pub)
    zpub = serialize_pub(ZPUB_VERSION, 3, parent_fp, HARDENED, c3, acc_pub)
    fingerprint = master_fp.hex()
    origin = f"[{fingerprint}/84h/0h/0h]{xpub}"
    return {
        "fingerprint": fingerprint,
        "path": ACCOUNT_PATH,
        "xpub": xpub,
        "zpub": zpub,
        "descriptor": add_descriptor_checksum(f"wpkh({origin}/0/*)"),
        "descriptor_change": add_descriptor_checksum(f"wpkh({origin}/1/*)"),
        "descriptor_multipath": add_descriptor_checksum(f"wpkh({origin}/<0;1>/*)"),
    }


def addresses_from_xpub(xpub: str, branch: int = 0, count: int = 3, start: int = 0) -> list[str]:
    """Direcciones bc1q derivadas solo desde la clave pública de la cuenta."""
    pt, chain = parse_xpub(xpub)
    bpt, bchain = ckd_pub(pt, chain, branch)
    out = []
    for idx in range(start, start + count):
        cpt, _ = ckd_pub(bpt, bchain, idx)
        out.append(segwit_v0_address(hash160(ser_p(cpt))))
    return out
