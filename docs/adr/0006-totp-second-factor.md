# ADR 0006 – TOTP second factor written with the standard library

**Status:** accepted (Sprint 6, story 6.1)

## Context
A manager account can change prices, grant discounts, refund money, manage
staff and read every guest's data. A password alone can be guessed, reused
from another site or watched over a shoulder at the front desk. Codes sent
by SMS or e-mail would need a paid gateway and an Internet connection.

## Decision
Time-based one-time passwords (RFC 6238), which every authenticator app
supports offline. The algorithm (HMAC-SHA1, dynamic truncation, 30-second
steps, ±1 step of drift) is about 20 lines in `domain/totp.py` using
`hmac`, `hashlib` and `base64`, so it can be explained line by line and is
tested against the RFCs' own test vectors. Only the QR code uses a library
(`segno`, pure Python, no dependencies), drawn as inline SVG on the server.

* Sign-in becomes two steps. After the password, the server stores a hashed
  challenge for 5 minutes and opens the session only after a valid code.
* The last accepted step is stored, so a code can never be replayed.
* Wrong codes count toward the same lockout as wrong passwords.
* Ten one-time recovery codes are shown once and stored as SHA-256 hashes.
* Managers must enrol: they get a 7-day reminder, after which every page
  leads to enrolment. Receptionists may opt in.
* `hotel reset-totp` is the last resort, with the same trust as
  `reset-password`: whoever runs commands on the server owns the data.

## Consequences
The shared secret is stored readable, because the server must compute codes.
A stolen database exposes it, but it is useless without the password, which
is protected by scrypt. A manager who loses both the phone and the recovery
codes needs someone with access to the server. WebAuthn (security keys)
would resist phishing better, but it needs JavaScript, which the CSP forbids.
