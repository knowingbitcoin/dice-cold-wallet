# Third-party notices

This project is under the MIT License ([LICENSE](LICENSE)). It also contains, or was checked against, the material below.

## Included in this repository

### DejaVu Sans font

- File: `coldwallet/ui/fonts/DejaVuSans.ttf`
- License: the Bitstream Vera / DejaVu font license, full text in `coldwallet/ui/fonts/DejaVu-LICENSE.txt`.
- The font is not covered by this project's MIT License.

### BIP39 English word list

- File: `crosscheck/english.txt`
- Source: `bip-0039/english.txt` in https://github.com/bitcoin/bips (SHA-256
  `2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda`, checked by `crosscheck/independent.py` at load time).
- BIP 39 is published under the MIT License.

### Snippet adapted from SeedSigner, and its dice examples

- In `tests/test_core.py`: the function `_seedsigner_generate_mnemonic_from_dice` is adapted from
  `generate_mnemonic_from_dice` in `src/seedsigner/helpers/mnemonic_generation.py`, and the two dice examples (24 and
  12 words) come from `docs/dice_verification.md`, both in https://github.com/SeedSigner/seedsigner.
- The tests use them only to check that the same rolls give the same words.

```
MIT License

Copyright (c) 2021 SeedSigner

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Test vectors

Copied by hand into `tests/` from their published sources:

- BIP39: the English vectors (16- and 32-byte entropy, passphrase "TREZOR") from `vectors.json` in
  https://github.com/trezor/python-mnemonic (MIT License, Copyright (c) 2013-2016 Pavol Rusnak).
- BIP32 (vectors 1 to 4), BIP84, BIP173 and BIP-380: from the specifications in https://github.com/bitcoin/bips.
- Descriptor examples from Bitcoin Core (`doc/descriptors.md` and `src/test/descriptor_tests.cpp`), https://github.com/bitcoin/bitcoin
  (MIT License, Copyright (c) 2009-2026 The Bitcoin Core developers).

## Dependencies (installed with pip, not included)

| Package | Version | License | Used for |
|---|---|---|---|
| embit | 0.8.0 | MIT | BIP39, BIP32 and descriptors in the wallet |
| qrcode | 8.2 | BSD | the QR code on screen |
| Pillow | 13.0.0 | MIT-CMU | drawing the screens (installed with apt on the Pi) |
| pytest | 9.2.0 | MIT | tests only |
| zxing-cpp | 3.1.1 | Apache-2.0 | tests only (reading the QR codes back) |

On the Pi, `spidev`, `gpiozero` and `lgpio` are installed with apt, as described in [README.es.md](README.es.md).
