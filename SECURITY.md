# Security policy

This project is a **prototype**. It has never run on the hardware it is designed for and it has had no external review. There
is no supported release. Do not use it for real savings (see the warning at the top of [README.md](README.md)).

Reviews are exactly what it needs, so reports are welcome.

## How to report

Report anything that could weaken the seed, leak the rolls, the phrase or a key, or make the device show a wrong public key
**privately**:

1. On GitHub: the **Security** tab of this repository → **Report a vulnerability** (private vulnerability reporting).
2. Or by email: **security@knowingbitcoin.com**.

Please do not open a public issue for these. Ordinary bugs with no security impact can go in a public issue.

## What to include

- What is wrong and why it matters.
- The commit you looked at.
- How to reproduce it, using **only the public test rolls** from the README, or rolls you made up for the test.

**Never send real dice rolls, real words, a real seed, private keys or an xpub/zpub of a wallet that holds funds.** If you
believe you have exposed a real seed while testing, move the funds to a new wallet first.

## What happens next

The report is read by the author. There is no fixed response time and no bug bounty. Confirmed issues are fixed in the
repository and described in the commit message once a fix is public.
