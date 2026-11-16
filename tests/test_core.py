"""Pruebas del núcleo de la cartera.

Todas las tiradas de este fichero son de PRUEBA y públicas.
SEMILLA DE PRUEBA — NO USAR para guardar dinero.
"""

import ast
import hashlib
import pathlib
import re

import pytest
from embit import bip32, bip39
from embit.descriptor import Descriptor

from coldwallet import core
from coldwallet.core import (
    ROLLS_FOR_WORDS,
    AccountInfo,
    derive_account,
    entropy_from_rolls,
    mnemonic_from_rolls,
    quiz_options,
    quiz_positions,
    receive_addresses,
    validate_rolls,
)

# Tiradas de PRUEBA fijas (SEMILLA DE PRUEBA — NO USAR).
TEST_ROLLS_24 = "123456" * 16 + "123"
TEST_ROLLS_12 = TEST_ROLLS_24[:50]


def test_test_rolls_lengths():
    assert len(TEST_ROLLS_24) == 99
    assert len(TEST_ROLLS_12) == 50
    assert ROLLS_FOR_WORDS == {12: 50, 24: 99}


# ---------------------------------------------------------------------------
# 1. Vectores oficiales de BIP39 (Trezor python-mnemonic, vectors.json, inglés)
#    Frase de contraseña: "TREZOR". Solo los de 16 y 32 bytes.
# ---------------------------------------------------------------------------

TREZOR_VECTORS = [
    # 16 bytes / 12 palabras
    (
        "00000000000000000000000000000000",
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about",
        "c55257c360c07c72029aebc1b53c05ed0362ada38ead3e3e9efa3708e53495531f09a6987599d18264c1e1c92f2cf141630c7a3c4ab7c81b2f001698e7463b04",
    ),
    (
        "7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f",
        "legal winner thank year wave sausage worth useful legal winner thank yellow",
        "2e8905819b8723fe2c1d161860e5ee1830318dbf49a83bd451cfb8440c28bd6fa457fe1296106559a3c80937a1c1069be3a3a5bd381ee6260e8d9739fce1f607",
    ),
    (
        "80808080808080808080808080808080",
        "letter advice cage absurd amount doctor acoustic avoid letter advice cage above",
        "d71de856f81a8acc65e6fc851a38d4d7ec216fd0796d0a6827a3ad6ed5511a30fa280f12eb2e47ed2ac03b5c462a0358d18d69fe4f985ec81778c1b370b652a8",
    ),
    (
        "ffffffffffffffffffffffffffffffff",
        "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo wrong",
        "ac27495480225222079d7be181583751e86f571027b0497b5b5d11218e0a8a13332572917f0f8e5a589620c6f15b11c61dee327651a14c34e18231052e48c069",
    ),
    (
        "9e885d952ad362caeb4efe34a8e91bd2",
        "ozone drill grab fiber curtain grace pudding thank cruise elder eight picnic",
        "274ddc525802f7c828d8ef7ddbcdc5304e87ac3535913611fbbfa986d0c9e5476c91689f9c8a54fd55bd38606aa6a8595ad213d4c9c9f9aca3fb217069a41028",
    ),
    (
        "c0ba5a8e914111210f2bd131f3d5e08d",
        "scheme spot photo card baby mountain device kick cradle pact join borrow",
        "ea725895aaae8d4c1cf682c1bfd2d358d52ed9f0f0591131b559e2724bb234fca05aa9c02c57407e04ee9dc3b454aa63fbff483a8b11de949624b9f1831a9612",
    ),
    (
        "23db8160a31d3e0dca3688ed941adbf3",
        "cat swing flag economy stadium alone churn speed unique patch report train",
        "deb5f45449e615feff5640f2e49f933ff51895de3b4381832b3139941c57b59205a42480c52175b6efcffaa58a2503887c1e8b363a707256bdd2b587b46541f5",
    ),
    (
        "f30f8c1da665478f49b001d94c5fc452",
        "vessel ladder alter error federal sibling chat ability sun glass valve picture",
        "2aaa9242daafcee6aa9d7269f17d4efe271e1b9a529178d7dc139cd18747090bf9d60295d0ce74309a78852a9caadf0af48aae1c6253839624076224374bc63f",
    ),
    # 32 bytes / 24 palabras
    (
        "0000000000000000000000000000000000000000000000000000000000000000",
        "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon art",
        "bda85446c68413707090a52022edd26a1c9462295029f2e60cd7c4f2bbd3097170af7a4d73245cafa9c3cca8d561a7c3de6f5d4a10be8ed2a5e608d68f92fcc8",
    ),
    (
        "7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f",
        "legal winner thank year wave sausage worth useful legal winner thank year wave sausage worth useful legal winner thank year wave sausage worth title",
        "bc09fca1804f7e69da93c2f2028eb238c227f2e9dda30cd63699232578480a4021b146ad717fbb7e451ce9eb835f43620bf5c514db0f8add49f5d121449d3e87",
    ),
    (
        "8080808080808080808080808080808080808080808080808080808080808080",
        "letter advice cage absurd amount doctor acoustic avoid letter advice cage absurd amount doctor acoustic avoid letter advice cage absurd amount doctor acoustic bless",
        "c0c519bd0e91a2ed54357d9d1ebef6f5af218a153624cf4f2da911a0ed8f7a09e2ef61af0aca007096df430022f7a2b6fb91661a9589097069720d015e4e982f",
    ),
    (
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo zoo vote",
        "dd48c104698c30cfe2b6142103248622fb7bb0ff692eebb00089b32d22484e1613912f0a5b694407be899ffd31ed3992c456cdf60f5d4564b8ba3f05a69890ad",
    ),
    (
        "68a79eaca2324873eacc50cb9c6eca8cc68ea5d936f98787c60c7ebc74e6ce7c",
        "hamster diagram private dutch cause delay private meat slide toddler razor book happy fancy gospel tennis maple dilemma loan word shrug inflict delay length",
        "64c87cde7e12ecf6704ab95bb1408bef047c22db4cc7491c4271d170a1b213d20b385bc1588d9c7b38f1b39d415665b8a9030c9ec653d75e65f847d8fc1fc440",
    ),
    (
        "066dca1a2bb7e8a1db2832148ce9933eea0f3ac9548d793112d9a95c9407efad",
        "all hour make first leader extend hole alien behind guard gospel lava path output census museum junior mass reopen famous sing advance salt reform",
        "26e975ec644423f4a4c4f4215ef09b4bd7ef924e85d1d17c4cf3f136c2863cf6df0a475045652c57eb5fb41513ca2a2d67722b77e954b4b3fc11f7590449191d",
    ),
    (
        "f585c11aec520db57dd353c69554b21a89b20fb0650966fa0a9d6f74fd989d8f",
        "void come effort suffer camp survey warrior heavy shoot primary clutch crush open amazing screen patrol group space point ten exist slush involve unfold",
        "01f5bced59dec48e362f2c45b5de68b9fd6c92c6634f44d6d40aab69056506f0e35524a518034ddc1192e1dacd32c1ed3eaa3c3b131c88ed8e7e54c49a5d0998",
    ),
]


@pytest.mark.parametrize("entropy_hex, phrase, seed_hex", TREZOR_VECTORS)
def test_trezor_bip39_vectors(entropy_hex, phrase, seed_hex):
    entropy = bytes.fromhex(entropy_hex)
    assert bip39.mnemonic_from_bytes(entropy) == phrase
    assert bip39.mnemonic_to_bytes(phrase) == entropy
    seed = bip39.mnemonic_to_seed(phrase, "TREZOR")
    assert seed.hex() == seed_hex
    # Comprobación independiente de embit: PBKDF2 de la biblioteca estándar.
    seed_std = hashlib.pbkdf2_hmac(
        "sha512", phrase.encode(), b"mnemonicTREZOR", 2048, 64
    )
    assert seed_std.hex() == seed_hex
    # derive_account usa la frase de contraseña como manda BIP39.
    info = derive_account(phrase.split(), "TREZOR")
    expected_fp = bip32.HDKey.from_seed(seed).my_fingerprint.hex()
    assert info.fingerprint == expected_fp


def test_trezor_first_vector_root_xprv():
    seed = bytes.fromhex(TREZOR_VECTORS[0][2])
    root = bip32.HDKey.from_seed(seed)
    assert root.to_base58() == (
        "xprv9s21ZrQH143K3h3fDYiay8mocZ3afhfULfb5GX8kCBdno77K4HiA15Tg23wpbeF1"
        "pLfs1c5SPmYHrEpTuuRhxMwvKDwqdKiGJS9XFKzUsAF"
    )


def test_trezor_vector_count():
    assert sum(len(e) == 32 for e, _, _ in TREZOR_VECTORS) == 8
    assert sum(len(e) == 64 for e, _, _ in TREZOR_VECTORS) == 7


# ---------------------------------------------------------------------------
# 2. Vector de BIP84
# ---------------------------------------------------------------------------

BIP84_PHRASE = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about"


def test_bip84_vector():
    info = derive_account(BIP84_PHRASE.split())
    assert isinstance(info, AccountInfo)
    assert info.fingerprint == "73c5da0a"
    assert info.path == "m/84'/0'/0'"
    assert info.zpub == (
        "zpub6rFR7y4Q2AijBEqTUquhVz398htDFrtymD9xYYfG1m4wAcvPhXNfE3EfH1r1ADqt"
        "fSdVCToUG868RvUUkgDKf31mGDtKsAYz2oz2AGutZYs"
    )
    assert info.xpub == (
        "xpub6CatWdiZiodmUeTDp8LT5or8nmbKNcuyvz7WyksVFkKB4RHwCD3XyuvPEbvqAQY3"
        "rAPshWcMLoP2fMFMKHPJ4ZeZXYVUhLv1VMrjPC7PW6V"
    )
    assert receive_addresses(info, 2) == [
        "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu",
        "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g",
    ]
    assert receive_addresses(info, 1, start=1) == [
        "bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g"
    ]
    # Primera dirección de cambio del mismo vector, a través del descriptor.
    change = Descriptor.from_string(info.descriptor_change).derive(0).address()
    assert change == "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el"


# Suma de control de descriptores según BIP-380, escrita aparte para no
# depender de embit al comprobarla.
_INPUT_CHARSET = (
    "0123456789()[],'/*abcdefgh@:$%{}"
    "IJKLMNOPQRSTUVWXYZ&+-.;<=>?!^_|~"
    "ijklmnopqrstuvwxyzABCDEFGH`#\"\\ "
)
_CHECKSUM_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"


def _polymod(c, val):
    c0 = c >> 35
    c = ((c & 0x7FFFFFFFF) << 5) ^ val
    for bit, gen in enumerate(
        (0xF5DEE51989, 0xA9FDCA3312, 0x1BAB10E32D, 0x3706B1677A, 0x644D626FFD)
    ):
        if c0 & (1 << bit):
            c ^= gen
    return c


def _bip380_checksum(desc):
    c, cls, clscount = 1, 0, 0
    for ch in desc:
        pos = _INPUT_CHARSET.find(ch)
        c = _polymod(c, pos & 31)
        cls = cls * 3 + (pos >> 5)
        clscount += 1
        if clscount == 3:
            c = _polymod(c, cls)
            cls, clscount = 0, 0
    if clscount:
        c = _polymod(c, cls)
    for _ in range(8):
        c = _polymod(c, 0)
    c ^= 1
    return "".join(_CHECKSUM_CHARSET[(c >> (5 * (7 - j))) & 31] for j in range(8))


def test_descriptors_format_and_checksum():
    info = derive_account(BIP84_PHRASE.split())
    for desc, branch in ((info.descriptor, "0"), (info.descriptor_change, "1")):
        body, checksum = desc.split("#")
        assert body == f"wpkh([73c5da0a/84h/0h/0h]{info.xpub}/{branch}/*)"
        assert checksum == _bip380_checksum(body)
        Descriptor.from_string(desc)  # embit también lo acepta
    assert info.descriptor.endswith("#afwvtk2s")
    first = Descriptor.from_string(info.descriptor).derive(0).address()
    assert first == receive_addresses(info, 1)[0]


# ---------------------------------------------------------------------------
# 3. Compatibilidad con SeedSigner (docs/dice_verification.md)
# ---------------------------------------------------------------------------


def _seedsigner_generate_mnemonic_from_dice(roll_data):
    """Adaptada de generate_mnemonic_from_dice (SeedSigner,
    src/seedsigner/helpers/mnemonic_generation.py; licencia MIT,
    Copyright (c) 2021 SeedSigner; ver THIRD_PARTY_NOTICES.md). Solo la lista inglesa."""
    entropy_bytes = hashlib.sha256(roll_data.encode()).digest()
    if len(roll_data) == 50:
        entropy_bytes = entropy_bytes[:16]
    return bip39.mnemonic_from_bytes(entropy_bytes).split()


# Ejemplos públicos de SeedSigner (docs/dice_verification.md).
# SEMILLA DE PRUEBA — NO USAR: cualquiera puede rehacerlas.
SEEDSIGNER_ROLLS_24 = (
    "655152231316521321611331544441236164664431121534415633526456254462"
    "245546236542364246312613322234612"
)
SEEDSIGNER_WORDS_24 = (
    "eyebrow obvious such suggest poet seven breeze blame virtual frown dynamic "
    "donor harsh pigeon express broccoli easy apology scatter force recipe "
    "shadow claim radio"
)
SEEDSIGNER_ROLLS_12 = "65515223131652132161133154444123616466443112153441"
SEEDSIGNER_WORDS_12 = (
    "hole luggage safe present express tragic orbit shed switch metal identify path"
)


def test_seedsigner_24_words_example():
    assert len(SEEDSIGNER_ROLLS_24) == 99
    words = mnemonic_from_rolls(SEEDSIGNER_ROLLS_24, 24)
    assert " ".join(words) == SEEDSIGNER_WORDS_24
    assert words == _seedsigner_generate_mnemonic_from_dice(SEEDSIGNER_ROLLS_24)
    # SeedSigner solo publica la huella, la xpub y las direcciones del ejemplo de
    # 24 palabras en capturas (docs/img/dicedoc/sesi_finger_print.png,
    # sparrow_wallet_2.png y coleman_addresses.png de su dice_verification.md).
    # Copiadas a mano de esas capturas el 16 nov 2026. SEMILLA DE PRUEBA — NO USAR.
    info = derive_account(words)
    assert info.fingerprint == "634a1f2e"
    assert info.xpub == (
        "xpub6BfhisZn1pCf8WkEo4k9Y5MsazGen1aaMpepf5g8diDAtcBb2NCGsFb7Mmha82tt"
        "m1DFGh4WKjKyfyi51B7zCmoMQZuosPzQA985HaQdjYv"
    )
    assert receive_addresses(info, 3) == [
        "bc1q0my23jqt97f6nurrwqvta2kdr0a9cdjphmamgg",
        "bc1qe9l64rkqy0tf4g90857aqyupnuh0xaw2rpnslx",
        "bc1q4clgpukjy44q4quqlt6lwacslwc8evqlwlh4wk",
    ]


def test_seedsigner_12_words_example():
    words = mnemonic_from_rolls(SEEDSIGNER_ROLLS_12, 12)
    assert " ".join(words) == SEEDSIGNER_WORDS_12
    assert words == _seedsigner_generate_mnemonic_from_dice(SEEDSIGNER_ROLLS_12)
    info = derive_account(words)
    assert info.fingerprint == "8d9cced8"
    assert info.zpub == (
        "zpub6qf9ziL759pzyhKMWaPfNSiCETkoA6oq3fbCDvXqcURiMtPnkEg3nH93W5mrSkvG"
        "PoJC9xTYZheYDsYoiYc5AkSk9iY3DkCJHkFgHMdijW6"
    )
    assert receive_addresses(info, 5) == [
        "bc1q00lln3r4mt4uwvg7mxv96xgpewauwmggkex2ff",
        "bc1q0jj2cv965f3642mv4lgq5za80jtfpkd0jhjefr",
        "bc1qpecssejm2678v0rknk9tsxd5fsshezfr0vr5m5",
        "bc1qcsl37xn5rkfz8qhcfwq5u52acxecyyfz0kv4gh",
        "bc1q8ehx53re0wck4m9tzek8mlnctp2ztm7jq94zm4",
    ]
    change = Descriptor.from_string(info.descriptor_change)
    assert [change.derive(i).address() for i in range(5)] == [
        "bc1qz0ckhg3m349qpmweyn5v6r6tvx2wfw4nv8h75q",
        "bc1qme5tu2t424ws3z69u445q0yw88vpc7fwygra4r",
        "bc1qznuyuc087ky7fhv4nvlmll4p586ks4ggcyt36d",
        "bc1qjcqxv22j0g00pehruwwh34sw5znu6vp3myaspy",
        "bc1q6dpfl7czd22wt0max6p09vr6lvvpag7xw9u8lc",
    ]


def test_entropy_is_sha256_of_rolls():
    full = hashlib.sha256(TEST_ROLLS_24.encode("ascii")).digest()
    assert entropy_from_rolls(TEST_ROLLS_24, 24) == full
    assert len(entropy_from_rolls(TEST_ROLLS_12, 12)) == 16
    assert entropy_from_rolls(TEST_ROLLS_12, 12) == (
        hashlib.sha256(TEST_ROLLS_12.encode("ascii")).digest()[:16]
    )


# ---------------------------------------------------------------------------
# 4. validate_rolls
# ---------------------------------------------------------------------------


def _bad_rolls_cases():
    good24 = TEST_ROLLS_24
    good12 = TEST_ROLLS_12
    cases = []
    for bad in ("0", "7", "a", "Z", " ", "9", "-", "\n", "١"):
        cases.append((good24[:-1] + bad, 24))
        cases.append((bad + good12[1:], 12))
    cases.append((good24[:50] + " " + good24[51:], 24))
    for n in (49, 51):
        cases.append(((good24 * 2)[:n], 12))
    for n in (98, 100, 0):
        cases.append(((good24 * 2)[:n], 24))
    return cases


@pytest.mark.parametrize("rolls, words", _bad_rolls_cases())
def test_validate_rolls_rejects(rolls, words):
    with pytest.raises(ValueError) as excinfo:
        validate_rolls(rolls, words)
    message = str(excinfo.value)
    assert message  # hay un mensaje para la persona
    # El mensaje nunca contiene las tiradas, ni siquiera un trozo largo.
    assert not re.search(r"[1-6]{6,}", message)
    if rolls:
        assert rolls not in message
    # Y las funciones que dependen de ella tampoco aceptan tiradas malas.
    with pytest.raises(ValueError):
        mnemonic_from_rolls(rolls, words)


def test_validate_rolls_rejects_bad_word_count():
    with pytest.raises(ValueError):
        validate_rolls(TEST_ROLLS_24, 18)


def test_validate_rolls_accepts_good():
    validate_rolls(TEST_ROLLS_24, 24)
    validate_rolls(TEST_ROLLS_12, 12)
    validate_rolls(SEEDSIGNER_ROLLS_24, 24)
    validate_rolls(SEEDSIGNER_ROLLS_12, 12)  # una cara en el 28 %: se acepta


@pytest.mark.parametrize(
    "rolls, words",
    [
        ("1" * 99, 24),
        ("6" * 50, 12),
        ("12" * 49 + "1", 24),  # el 1 sale en la mitad de las tiradas
        ("1" * 16 + TEST_ROLLS_24[16:50], 12),  # 16 de 50 = 32 %
        ("5" * 8 + TEST_ROLLS_24[8:], 24),  # 8 iguales seguidas
    ],
)
def test_degenerate_rolls_rejected(rolls, words):
    """Tiradas que no parecen al azar dan semillas que se adivinan: se rechazan."""
    assert core.rolls_quality_problem(rolls)
    with pytest.raises(ValueError) as excinfo:
        mnemonic_from_rolls(rolls, words)
    assert not re.search(r"[1-6]{6,}", str(excinfo.value))


def test_quality_limits_exact():
    # 15 unos de 50 (30 %) se acepta; 16 (32 %), no.
    fifteen = "1213141516" * 3 + "23456" * 4
    assert len(fifteen) == 50 and fifteen.count("1") == 15
    assert core.rolls_quality_problem(fifteen) is None
    sixteen = fifteen[:-1] + "1"
    assert sixteen.count("1") == 16
    assert core.rolls_quality_problem(sixteen)
    # Racha de 7 iguales se acepta; de 8, no.
    assert core.rolls_quality_problem("5" * 7 + TEST_ROLLS_24[7:]) is None
    assert core.rolls_quality_problem("5" * 8 + TEST_ROLLS_24[8:])


def test_derive_account_error_does_not_leak_words():
    words = mnemonic_from_rolls(TEST_ROLLS_12, 12)
    broken = words[:-1] + ["notaword"]
    with pytest.raises(ValueError) as excinfo:
        derive_account(broken)
    message = str(excinfo.value)
    for word in broken:
        assert word not in message
    assert excinfo.value.__cause__ is None
    # Checksum incorrecto: se cambia la última palabra por otra de la lista.
    wrong_last = words[:-1] + ["zoo" if words[-1] != "zoo" else "abandon"]
    if not bip39.mnemonic_is_valid(" ".join(wrong_last)):
        with pytest.raises(ValueError) as excinfo:
            derive_account(wrong_last)
        for word in wrong_last:
            assert word not in str(excinfo.value)


# ---------------------------------------------------------------------------
# 5. Regresión con las tiradas de PRUEBA fijas (SEMILLA DE PRUEBA — NO USAR)
# ---------------------------------------------------------------------------

TEST_PHRASE_24 = (
    "few educate sugar bless boring random strategy waste mutual cargo type hawk "
    "prefer denial scan abstract filter extend dignity balcony dust unusual "
    "correct bubble"
)
TEST_PHRASE_12 = (
    "unveil nice picture region tragic fault cream strike tourist control recipe tourist"
)


def test_regression_test_rolls_24():
    words = mnemonic_from_rolls(TEST_ROLLS_24, 24)
    assert " ".join(words) == TEST_PHRASE_24
    assert mnemonic_from_rolls(TEST_ROLLS_24, 24) == words  # determinista
    info = derive_account(words)
    assert info.fingerprint == "5545de0e"
    assert info.zpub == (
        "zpub6qbjoXQDYXJGb9vWNZ8BGwriWDQkd1qCUKXkb4kzDHuei8PNS2m4xsYqqQ2JcRyv"
        "nxBb3dFR2WFUy9DcNKoXKG9xMiNnFEmbCRoysJKF511"
    )
    assert info.descriptor.endswith("#8v6d7nx2")
    assert info.descriptor_change.endswith("#kclvrxkj")
    assert receive_addresses(info) == [
        "bc1qvjc0ndgk8ap8uy495enag3qtcl4lua6nn3uyys",
        "bc1qwazuu4zpl9j2julxq4gv2s0d3y3tw3p9z4s79s",
        "bc1qfzvrcl5ysvmdxyna8edke2vat75kdaaamhnna5",
    ]


def test_regression_test_rolls_12():
    words = mnemonic_from_rolls(TEST_ROLLS_12, 12)
    assert " ".join(words) == TEST_PHRASE_12
    info = derive_account(words)
    assert info.fingerprint == "85480bc5"
    assert receive_addresses(info, 1) == ["bc1q40jg305efx4r2h9nmp7zr25supg58vpzcgx54e"]


def test_passphrase_changes_account():
    words = mnemonic_from_rolls(TEST_ROLLS_24, 24)
    assert derive_account(words, "otra").fingerprint != derive_account(words).fingerprint
    # BIP39: la frase de contraseña se normaliza en NFKD.
    composed = "é"  # é en una sola letra
    decomposed = "é"  # e + tilde aparte
    assert derive_account(words, composed) == derive_account(words, decomposed)


def test_account_info_is_frozen():
    info = derive_account(BIP84_PHRASE.split())
    with pytest.raises(Exception):
        info.xpub = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6. Examen de palabras
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_words", [12, 24])
def test_quiz_positions(n_words):
    for _ in range(200):
        positions = quiz_positions(n_words)
        assert len(positions) == 3
        assert len(set(positions)) == 3
        assert positions == sorted(positions)
        assert all(1 <= p <= n_words for p in positions)


def test_quiz_positions_bad_count():
    with pytest.raises(ValueError):
        quiz_positions(12, 13)
    with pytest.raises(ValueError):
        quiz_positions(12, 0)


@pytest.mark.parametrize("rolls, words", [(TEST_ROLLS_24, 24), (TEST_ROLLS_12, 12)])
def test_quiz_options(rolls, words):
    mnemonic = mnemonic_from_rolls(rolls, words)
    for position in range(1, words + 1):
        for _ in range(20):
            options = quiz_options(mnemonic, position)
            assert len(options) == 4
            assert len(set(options)) == 4
            assert mnemonic[position - 1] in options
            assert all(o in bip39.WORDLIST for o in options)
            # Los señuelos son otras palabras de la misma frase.
            assert set(options) <= set(mnemonic)


def test_quiz_options_short_phrase_fills_from_wordlist():
    mnemonic = ("abandon " * 11 + "about").split()  # solo 2 palabras distintas
    for position in (1, 12):
        options = quiz_options(mnemonic, position)
        assert len(options) == len(set(options)) == 4
        assert mnemonic[position - 1] in options
        assert all(o in bip39.WORDLIST for o in options)


def test_quiz_positions_all_words():
    assert quiz_positions(24, 24) == list(range(1, 25))


def test_quiz_options_shuffles():
    mnemonic = mnemonic_from_rolls(TEST_ROLLS_24, 24)
    places = {quiz_options(mnemonic, 1).index(mnemonic[0]) for _ in range(200)}
    assert len(places) > 1  # la correcta no está siempre en el mismo sitio


def test_quiz_options_bad_position():
    mnemonic = mnemonic_from_rolls(TEST_ROLLS_12, 12)
    with pytest.raises(ValueError):
        quiz_options(mnemonic, 0)
    with pytest.raises(ValueError):
        quiz_options(mnemonic, 13)


# ---------------------------------------------------------------------------
# Reglas de seguridad comprobables en el código
# ---------------------------------------------------------------------------

_FORBIDDEN_MODULES = {
    "socket", "requests", "urllib", "urllib3", "http", "httpx", "aiohttp",
    "ftplib", "smtplib", "telnetlib", "ssl", "random", "logging", "pickle",
}


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_core_has_no_network_random_or_logging():
    package = pathlib.Path(core.__file__).parent
    for path in package.glob("*.py"):
        assert not (_imported_modules(path) & _FORBIDDEN_MODULES), path.name
        assert not ({"print", "open", "eval", "exec"} & _calls(path)), path.name
