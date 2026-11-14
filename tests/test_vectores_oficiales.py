"""Vectores oficiales que no dependen de las tiradas: BIP32, BIP173 y BIP-380.

Copiados a mano de las fuentes (sin descargar nada al pasar las pruebas):
- BIP32, vectores 1 a 4: https://github.com/bitcoin/bips/blob/master/bip-0032.mediawiki
- BIP173: https://github.com/bitcoin/bips/blob/master/bip-0173.mediawiki
- BIP-380 y pruebas de descriptores de Bitcoin Core (src/test/descriptor_tests.cpp).

Sirven de red: si un día se actualiza embit o se toca crosscheck/independent.py
y las dos implementaciones fallan a la vez, estos vectores lo detectan.
"""

import pytest
from embit import bip32, script
from embit.descriptor import Descriptor
from embit.descriptor.checksum import add_checksum
from embit.networks import NETWORKS

from coldwallet import core
from crosscheck import independent as ind

BIP32_VECTORS = [('1',
  '000102030405060708090a0b0c0d0e0f',
  [('m',
    'xpub661MyMwAqRbcFtXgS5sYJABqqG9YLmC4Q1Rdap9gSE8NqtwybGhePY2gZ29ESFjqJoCu1Rupje8YtGqsefD265TMg7usUDFdp6W1EGMcet8',
    'xprv9s21ZrQH143K3QTDL4LXw2F7HEK3wJUD2nW2nRk4stbPy6cq3jPPqjiChkVvvNKmPGJxWUtg6LnF5kejMRNNU3TGtRBeJgk33yuGBxrMPHi'),
   ("m/0'",
    'xpub68Gmy5EdvgibQVfPdqkBBCHxA5htiqg55crXYuXoQRKfDBFA1WEjWgP6LHhwBZeNK1VTsfTFUHCdrfp1bgwQ9xv5ski8PX9rL2dZXvgGDnw',
    'xprv9uHRZZhk6KAJC1avXpDAp4MDc3sQKNxDiPvvkX8Br5ngLNv1TxvUxt4cV1rGL5hj6KCesnDYUhd7oWgT11eZG7XnxHrnYeSvkzY7d2bhkJ7'),
   ("m/0'/1",
    'xpub6ASuArnXKPbfEwhqN6e3mwBcDTgzisQN1wXN9BJcM47sSikHjJf3UFHKkNAWbWMiGj7Wf5uMash7SyYq527Hqck2AxYysAA7xmALppuCkwQ',
    'xprv9wTYmMFdV23N2TdNG573QoEsfRrWKQgWeibmLntzniatZvR9BmLnvSxqu53Kw1UmYPxLgboyZQaXwTCg8MSY3H2EU4pWcQDnRnrVA1xe8fs'),
   ("m/0'/1/2'",
    'xpub6D4BDPcP2GT577Vvch3R8wDkScZWzQzMMUm3PWbmWvVJrZwQY4VUNgqFJPMM3No2dFDFGTsxxpG5uJh7n7epu4trkrX7x7DogT5Uv6fcLW5',
    'xprv9z4pot5VBttmtdRTWfWQmoH1taj2axGVzFqSb8C9xaxKymcFzXBDptWmT7FwuEzG3ryjH4ktypQSAewRiNMjANTtpgP4mLTj34bhnZX7UiM'),
   ("m/0'/1/2'/2",
    'xpub6FHa3pjLCk84BayeJxFW2SP4XRrFd1JYnxeLeU8EqN3vDfZmbqBqaGJAyiLjTAwm6ZLRQUMv1ZACTj37sR62cfN7fe5JnJ7dh8zL4fiyLHV',
    'xprvA2JDeKCSNNZky6uBCviVfJSKyQ1mDYahRjijr5idH2WwLsEd4Hsb2Tyh8RfQMuPh7f7RtyzTtdrbdqqsunu5Mm3wDvUAKRHSC34sJ7in334'),
   ("m/0'/1/2'/2/1000000000",
    'xpub6H1LXWLaKsWFhvm6RVpEL9P4KfRZSW7abD2ttkWP3SSQvnyA8FSVqNTEcYFgJS2UaFcxupHiYkro49S8yGasTvXEYBVPamhGW6cFJodrTHy',
    'xprvA41z7zogVVwxVSgdKUHDy1SKmdb533PjDz7J6N6mV6uS3ze1ai8FHa8kmHScGpWmj4WggLyQjgPie1rFSruoUihUZREPSL39UNdE3BBDu76')]),
 ('2',
  'fffcf9f6f3f0edeae7e4e1dedbd8d5d2cfccc9c6c3c0bdbab7b4b1aeaba8a5a29f9c999693908d8a8784817e7b7875726f6c696663605d5a5754514e4b484542',
  [('m',
    'xpub661MyMwAqRbcFW31YEwpkMuc5THy2PSt5bDMsktWQcFF8syAmRUapSCGu8ED9W6oDMSgv6Zz8idoc4a6mr8BDzTJY47LJhkJ8UB7WEGuduB',
    'xprv9s21ZrQH143K31xYSDQpPDxsXRTUcvj2iNHm5NUtrGiGG5e2DtALGdso3pGz6ssrdK4PFmM8NSpSBHNqPqm55Qn3LqFtT2emdEXVYsCzC2U'),
   ('m/0',
    'xpub69H7F5d8KSRgmmdJg2KhpAK8SR3DjMwAdkxj3ZuxV27CprR9LgpeyGmXUbC6wb7ERfvrnKZjXoUmmDznezpbZb7ap6r1D3tgFxHmwMkQTPH',
    'xprv9vHkqa6EV4sPZHYqZznhT2NPtPCjKuDKGY38FBWLvgaDx45zo9WQRUT3dKYnjwih2yJD9mkrocEZXo1ex8G81dwSM1fwqWpWkeS3v86pgKt'),
   ("m/0/2147483647'",
    'xpub6ASAVgeehLbnwdqV6UKMHVzgqAG8Gr6riv3Fxxpj8ksbH9ebxaEyBLZ85ySDhKiLDBrQSARLq1uNRts8RuJiHjaDMBU4Zn9h8LZNnBC5y4a',
    'xprv9wSp6B7kry3Vj9m1zSnLvN3xH8RdsPP1Mh7fAaR7aRLcQMKTR2vidYEeEg2mUCTAwCd6vnxVrcjfy2kRgVsFawNzmjuHc2YmYRmagcEPdU9'),
   ("m/0/2147483647'/1",
    'xpub6DF8uhdarytz3FWdA8TvFSvvAh8dP3283MY7p2V4SeE2wyWmG5mg5EwVvmdMVCQcoNJxGoWaU9DCWh89LojfZ537wTfunKau47EL2dhHKon',
    'xprv9zFnWC6h2cLgpmSA46vutJzBcfJ8yaJGg8cX1e5StJh45BBciYTRXSd25UEPVuesF9yog62tGAQtHjXajPPdbRCHuWS6T8XA2ECKADdw4Ef'),
   ("m/0/2147483647'/1/2147483646'",
    'xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL',
    'xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc'),
   ("m/0/2147483647'/1/2147483646'/2",
    'xpub6FnCn6nSzZAw5Tw7cgR9bi15UV96gLZhjDstkXXxvCLsUXBGXPdSnLFbdpq8p9HmGsApME5hQTZ3emM2rnY5agb9rXpVGyy3bdW6EEgAtqt',
    'xprvA2nrNbFZABcdryreWet9Ea4LvTJcGsqrMzxHx98MMrotbir7yrKCEXw7nadnHM8Dq38EGfSh6dqA9QWTyefMLEcBYJUuekgW4BYPJcr9E7j')]),
 ('3',
  '4b381541583be4423346c643850da4b320e46a87ae3d2a4e6da11eba819cd4acba45d239319ac14f863b8d5ab5a0d0c64d2e8a1e7d1457df2e5a3c51c73235be',
  [('m',
    'xpub661MyMwAqRbcEZVB4dScxMAdx6d4nFc9nvyvH3v4gJL378CSRZiYmhRoP7mBy6gSPSCYk6SzXPTf3ND1cZAceL7SfJ1Z3GC8vBgp2epUt13',
    'xprv9s21ZrQH143K25QhxbucbDDuQ4naNntJRi4KUfWT7xo4EKsHt2QJDu7KXp1A3u7Bi1j8ph3EGsZ9Xvz9dGuVrtHHs7pXeTzjuxBrCmmhgC6'),
   ("m/0'",
    'xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y',
    'xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L')]),
 ('4',
  '3ddd5602285899a946114506157c7997e5444528f3003f6134712147db19b678',
  [('m',
    'xpub661MyMwAqRbcGczjuMoRm6dXaLDEhW1u34gKenbeYqAix21mdUKJyuyu5F1rzYGVxyL6tmgBUAEPrEz92mBXjByMRiJdba9wpnN37RLLAXa',
    'xprv9s21ZrQH143K48vGoLGRPxgo2JNkJ3J3fqkirQC2zVdk5Dgd5w14S7fRDyHH4dWNHUgkvsvNDCkvAwcSHNAQwhwgNMgZhLtQC63zxwhQmRv'),
   ("m/0'",
    'xpub69AUMk3qDBi3uW1sXgjCmVjJ2G6WQoYSnNHyzkmdCHEhSZ4tBok37xfFEqHd2AddP56Tqp4o56AePAgCjYdvpW2PU2jbUPFKsav5ut6Ch1m',
    'xprv9vB7xEWwNp9kh1wQRfCCQMnZUEG21LpbR9NPCNN1dwhiZkjjeGRnaALmPXCX7SgjFTiCTT6bXes17boXtjq3xLpcDjzEuGLQBM5ohqkao9G'),
   ("m/0'/1'",
    'xpub6BJA1jSqiukeaesWfxe6sNK9CCGaujFFSJLomWHprUL9DePQ4JDkM5d88n49sMGJxrhpjazuXYWdMf17C9T5XnxkopaeS7jGk1GyyVziaMt',
    'xprv9xJocDuwtYCMNAo3Zw76WENQeAS6WGXQ55RCy7tDJ8oALr4FWkuVoHJeHVAcAqiZLE7Je3vZJHxspZdFHfnBEjHqU5hG1Jaj32dVoS6XLT1')])]

CASES = [(num, seed, path, xpub, xprv) for num, seed, chains in BIP32_VECTORS
         for path, xpub, xprv in chains]


def _independent(seed: bytes, path: str) -> tuple[str, str]:
    k, c = ind.master_key(seed)
    depth, parent_fp, child = 0, b"\0" * 4, 0
    for comp in path.split("/")[1:]:
        hardened = comp.endswith("'")
        index = int(comp.rstrip("'")) + (ind.HARDENED if hardened else 0)
        parent_fp = ind.hash160(ind.ser_p(ind.point_mul(k)))[:4]
        k, c = ind.ckd_priv(k, c, index)
        depth += 1
        child = index
    xpub = ind.serialize_pub(ind.XPUB_VERSION, depth, parent_fp, child, c, ind.point_mul(k))
    xprv = ind.base58check(
        bytes.fromhex("0488ADE4") + bytes([depth]) + parent_fp + child.to_bytes(4, "big")
        + c + b"\0" + k.to_bytes(32, "big")
    )
    return xpub, xprv


def test_bip32_vector_count():
    assert len(CASES) == 17


@pytest.mark.parametrize("num, seed, path, xpub, xprv", CASES, ids=[f"tv{c[0]}-{c[2]}" for c in CASES])
def test_bip32_official_vectors(num, seed, path, xpub, xprv):
    root = bip32.HDKey.from_seed(bytes.fromhex(seed))
    node = root.derive(path) if path != "m" else root
    assert node.to_base58() == xprv
    assert node.to_public().to_base58() == xpub
    assert _independent(bytes.fromhex(seed), path) == (xpub, xprv)


def test_bip32_public_derivation_vector_2():
    _, _, chains = BIP32_VECTORS[1]
    master_xpub, child_xpub = chains[0][1], chains[1][1]
    assert bip32.HDKey.from_string(master_xpub).derive([0]).to_base58() == child_xpub
    pt, chain = ind.parse_xpub(master_xpub)
    cpt, cchain = ind.ckd_pub(pt, chain, 0)
    fp = ind.hash160(ind.ser_p(pt))[:4]
    assert ind.serialize_pub(ind.XPUB_VERSION, 1, fp, 0, cchain, cpt) == child_xpub


def test_bip173_address():
    program = bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")
    expected = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
    assert ind.segwit_v0_address(program) == expected
    assert script.Script(bytes.fromhex("0014") + program).address(NETWORKS["main"]) == expected


DESCRIPTOR_VECTORS = [
    "raw(deadbeef)#89f8spxm",
    "sh(multi(2,[00000000/111'/222]xprvA1RpRA33e1JQ7ifknakTFpgNXPmW2YvmhqLQYMmrj4xJXXWYpDPS3xz7iAxn8L39njGVyuoseXzU6rcxFLJ8HFsTjSyQbLYnMpCqE2VbFWc,xprv9uPDJpEQgRQfDcW7BkF7eTya6RPxXeJCqCJGHuCJ4GiRVLzkTXBAJMu2qaMWPrS7AANYqdq6vcBcBUdJCVVFceUvJFjaPdGZ2y9WACViL4L/0))#ggrsrxfy",
    "sh(multi(2,[00000000/111'/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#tjg09x5t",
    "sh(multi(2,[00000000/111h/222]xpub6ERApfZwUNrhLCkDtcHTcxd75RbzS1ed54G1LkBUHQVHQKqhMkhgbmJbZRkrgZw4koxb5JaHWkY4ALHY2grBGRjaDMzQLcgJvLJuZZvRcEL,xpub68NZiKmJWnxxS6aaHmn81bvJeTESw724CRDs6HbuccFQN9Ku14VQrADWgqbhhTHBaohPX4CjNLf9fq9MYo6oDaPPLPxSb7gwQN3ih19Zm4Y/0))#hgmsckna",
    "rawtr([5a61ff8e/86h/1h/0h]xpub6DtZpc9PRL2B6pwoNGysmHAaBofDmWv5S6KQEKKGPKhf5fV62ywDtSziSApYVK3JnYY5KUSgiCwiXW5wtd8z7LNBxT9Mu5sEro8itdGfTeA/1/*)#vwgx7hj9",
]


@pytest.mark.parametrize("vector", DESCRIPTOR_VECTORS, ids=range(len(DESCRIPTOR_VECTORS)))
def test_descriptor_checksum_official(vector):
    body = vector.split("#")[0]
    assert add_checksum(body) == vector
    assert ind.add_descriptor_checksum(body) == vector


def test_multipath_descriptor_bip84_vector():
    """El descriptor de dos ramas lleva a la dirección de cobro y a la de cambio de BIP84."""
    mnemonic = ("abandon " * 11 + "about").split()
    info = core.derive_account(mnemonic)
    assert info.descriptor_multipath.split("#")[0].endswith("/<0;1>/*)")
    desc = Descriptor.from_string(info.descriptor_multipath)
    assert desc.derive(0, branch_index=0).address(NETWORKS["main"]) == (
        "bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu"
    )
    assert desc.derive(0, branch_index=1).address(NETWORKS["main"]) == (
        "bc1q8c6fshw2dlwun7ekn9qwf37cu2rn755upcp6el"
    )
    assert ind.derive_account(mnemonic)["descriptor_multipath"] == info.descriptor_multipath
