# Security design

This is the threat review done before writing code, with the status of each
control. Severity: 🔴 critical · 🟠 high · 🟡 medium · ⚪ low.
Status: ✅ done (with tests) · ⏳ planned (sprint).

## Authentication, sessions and roles

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| A1 | 🔴 | Default credentials | No built-in account; `hotel create-manager` asks for the password | ✅ S1 |
| A2 | 🔴 | Signed-cookie sessions cannot be revoked | Server-side `user_session` table; cookie holds a random 256-bit token; only its SHA-256 is stored | ✅ S1 |
| A3 | 🟠 | Password guessing, user enumeration | Lockout after 5 failures, doubling up to 24 h; per-address throttle (20 / 15 min); identical message; dummy hash for unknown users | ✅ S1 |
| A4 | 🟠 | Weak passwords | scrypt (n=2¹⁵, r=8, p=1, 16-byte salt); ≥ 12 characters; common-password blocklist; no username inside | ✅ S1 |
| A5 | 🟠 | A route forgets its role check | Deny by default; every view declares `@public`, `@login_required` or `@roles_required`; a test walks every route; services re-check roles | ✅ S1–S2 |
| A6 | 🟠 | Receptionist grants own discounts or large refunds | Discounts and refunds manager-only (role re-checked in the service), capped, reason required, audited | ✅ S4 |
| A7 | 🟡 | Session fixation | New token at every login, previous one destroyed | ✅ S1 |
| A8 | 🟡 | Last manager deactivated or demoted; manager deactivating self | Refused | ✅ S2 |
| A9 | 🟡 | Manager knows a reset password | `must_change_password` blocks every page until changed; reset ends sessions | ✅ S2 |
| A10 | 🟡 | Missing traceability | Hash-chained, append-only audit log (triggers + SHA-256 chain); `hotel audit verify`; manager viewer | ✅ S2 |
| A11 | ⚪ | TOTP replay | The last accepted time step is stored; a code of that step or an earlier one is refused (RFC 6238 §5.2) | ✅ S6 |
| A12 | 🟠 | A stolen manager password alone opens every manager page | TOTP second factor (RFC 6238, standard library, RFC test vectors); required for managers after a 7-day grace period (pages blocked until enrolled); the session opens only after the code (hashed 5-minute challenge, 5 tries); wrong codes count toward the account lockout (A3); 10 one-time recovery codes stored as SHA-256; enrolment confirmed by one code; `hotel reset-totp` for a lost phone; every step audited | ✅ S6 |
| A14 | 🟡 | Cookies planted or read over the network | Behind HTTPS every cookie is `__Host-` prefixed and `Secure`; session cookies `HttpOnly`, `SameSite=Lax`; sign-out sends `Clear-Site-Data` | ✅ S6 |
| A13 | ⚪ | The TOTP secret is readable in a stolen database | Accepted: the secret must be readable to compute codes. It is useless without the scrypt-protected password, and a stolen database already exposes everything else; backups are protected like the database | ✅ S6 (accepted) |

## Web

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| W1 | 🔴 | Werkzeug debugger in production (remote code execution) | Production is the default; Waitress never enables debug; start-up refuses `FLASK_DEBUG` in production | ✅ S1 |
| W2 | 🔴 | Secret key in Git or weak | Generated on first start in `instance/` (git-ignored, mode 0600); weak keys refused | ✅ S1 |
| W3 | 🟠 | Passwords in clear text on the LAN | Binds to 127.0.0.1 by default; LAN mode documented with Caddy HTTPS; warning printed | ✅ S1 (docs) |
| W4 | 🟠 | Missing security headers | CSP (`default-src 'self'`, no inline scripts or styles, `frame-ancestors 'none'`), `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP, HSTS behind HTTPS | ✅ S1 |
| W5 | 🟠 | Back button shows guest data after logout | `Cache-Control: no-store` on every page | ✅ S1 |
| W6 | 🟡 | IDOR | Role per object type checked in every service; personal objects (own password, second factor, API tokens) checked against their owner | ✅ S2–S6 |
| W7 | 🟡 | Stack traces leak | Generic 500 page with incident id | ✅ S1 |
| W8 | 🟡 | Vulnerable dependencies | pip-audit in CI, Dependabot | ✅ S1 |
| W9 | ⚪ | Expensive report ranges | 2-year cap (731 nights), tested | ✅ S5 |
| W10 | ⚪ | File uploads | None by design | ✅ |
| W11 | 🟡 | A compromised container gains root or persists | Image runs as uid 10001; compose: read-only file system, all capabilities dropped, `no-new-privileges`; dependencies installed only from hash-checked wheels; app port reachable only through Caddy (HTTPS) | ✅ S6 |
| W12 | 🟠 | JSON API used to steal or change data | Read-only (GET only); bearer tokens of 256 bits, shown once, stored as SHA-256, expiring (≤ 365 days), revocable, tied to an active manager; cookie sessions refused on `/api/` (no CSRF); 120 calls/min per manager, 10 wrong tokens/min per address; same service-layer role checks; creation and revocation audited | ✅ S6 |

## Input validation and injection

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| I1 | 🔴 | SQL injection | Every query uses `?` parameters; sorting through whitelists; `LIKE` escaping; bandit in CI; injection strings in search tests | ✅ S2 |
| I2 | 🟠 | XSS | Jinja autoescaping, no `|safe` on user data, strict CSP; test with a `<script>` name | ✅ S1 |
| I3 | 🟠 | CSRF | Flask-WTF on every POST; logout and preferences are POST; `SameSite=Lax` | ✅ S1 |
| I4 | 🟠 | Trusting hidden form fields | Server recomputes prices; whitelisted preference values | ✅ S1–S3 |
| I5 | 🟡 | CSV formula injection | Text cells starting with = + - @ tab or line break prefixed with an apostrophe; tested | ✅ S5 |
| I6 | 🟡 | Open redirect via `?next=` | Only same-site relative paths | ✅ S1 |
| I7 | 🟡 | Language/theme cookie tampering | Whitelists | ✅ S1 |
| I8 | ⚪ | Oversized input | `MAX_CONTENT_LENGTH` 1 MB, field length limits, NFKC normalisation | ✅ S1 |

## Data integrity, money, privacy, concurrency

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| D1 | 🔴 | Foreign keys off by default | Enabled on every connection, tested | ✅ S1 |
| D2 | 🔴 | Inconsistent file-copy backups | SQLite online backup API, integrity check, atomic rename, daily rotation, backup before upgrades, safety copy before restore | ✅ S2 |
| D3 | 🟠 | Partial writes | Unit of Work transactions; failure-injection test | ✅ S1 |
| D4 | 🟠 | Failed migration | One transaction per migration; refuse newer schemas; automatic backup before upgrading | ✅ S2 |
| D5 | 🟡 | Undetected corruption | `quick_check` at start-up | ✅ S1 |
| F1–F4 | 🟠 | Float errors, banker's rounding, locale input | Integer millimes, explicit half-up per line, "180,5" and "7,5 %" accepted, no thousands separators | ✅ S1–S4 |
| F5 | 🟠 | Altered or deleted money records | Payments append-only and issued invoices immutable (triggers); corrections are new entries (refunds, voided charges kept); invoice numbers gap-free in the same transaction | ✅ S4 |
| F6 | 🟡 | Typing errors become refunds to chase | Payments never above the balance due, refunds never above the overpayment | ✅ S4 |
| P1–P6 | 🟠 | Guest personal data | Masked ID numbers, audited reveal (never stored in cookies or URLs), no PII in audit details or CSV exports; manager-confirmed anonymisation after a configurable time (default 24 months), invoices keep their copy | ✅ S2–S5 |
| C1 | 🔴 | Double booking race | `BEGIN IMMEDIATE` + recheck + `room_night` primary key; two-thread race test | ✅ S3 |
| C2 | 🟠 | Lost updates | `version` column on users, rooms, categories, guests, reservations, extras and tax rules; `StaleDataError` | ✅ S1–S4 |
| C3 | 🟠 | Double submit | One-time form tokens (owner-bound, 8 h, hashed) on booking, change, cancel, charges, payments and refunds; version checks on check-in/out | ✅ S3–S4 |

## Accepted limitations

* The database file and backups are not encrypted at rest: protect them with
  OS permissions and full-disk encryption (BitLocker / LUKS).
* Without a TLS reverse proxy, LAN use exposes passwords on the network.
* The common-password list holds the 7,309 most frequent passwords of 12+
  characters from public breach lists (SecLists); it cannot catch every
  predictable password.

The OWASP ASVS 5.0 Level 1 self-assessment is in [asvs.md](asvs.md).

## Authorization matrix

Two roles. Every route declares its policy (deny by default) and every
service method checks the role again; the table is generated from the
application's routes (`e2e/test_route_policy.py` fails if one is missing).

| Area | Anyone | Receptionist | Manager |
|---|---|---|---|
| Sign in, sign out, language and theme, `/health` | ✅ | ✅ | ✅ |
| Dashboard, availability, room list and room page, housekeeping state | | ✅ | ✅ |
| Guests: search, register, edit, flags, reveal a document (audited) | | ✅ | ✅ |
| Reservations: book, change, move rooms (keeping the price), cancel, check in, no-show, check out | | ✅ | ✅ |
| Extras charged to a stay; payments; bills and invoices (read) | | ✅ | ✅ |
| Own password; own two-factor sign-in (managers cannot turn it off) | | ✅ | ✅ |
| Move rooms at the new room's price; void a charge; discounts; refunds; tax exemptions for a stay | | | ✅ |
| Rooms, categories, prices and rate periods, maintenance | | | ✅ |
| Extras catalogue, hotel settings, tax rules | | | ✅ |
| Staff accounts (create, edit, deactivate, reset password, unlock) | | | ✅ |
| Reports and CSV exports, night audit, audit log, backups | | | ✅ |
| Guest anonymisation | | | ✅ |
| Remove (delete if never used, otherwise archive) and restore guests, rooms, services, tax rules, accounts | | | ✅ |
| Own API tokens; the read-only JSON API with such a token | | | ✅ |
| Command line (`create-manager`, `reset-password`, `reset-totp`, `restore`…) | whoever can run commands on the server: they already own the data | | |

Data-level rule: one hotel, one team, so staff see every guest and every
reservation; objects that belong to a person (password, second factor, API
tokens) are only reachable by their owner.

## Input validation rules

All checks run in `domain/` (called by the services), never only in the
browser. Text is NFC/NFKC-normalised and trimmed; every request body is
capped at 1 MB.

| Data | Rule |
|---|---|
| Username | 3–32 characters `a-z 0-9 . _ -`, stored lower case (NFKC) |
| Password | 12–128 characters, not mostly one character, not containing the username, not in the common list; any characters allowed |
| Full name; guest first/last name | 1–100 characters; 1–60 letters (any alphabet) with spaces, hyphens, apostrophes and dots |
| Identity document | CIN: 8 digits; passport: 6–9 letters and digits with at least one digit (ICAO 9303); unique per type |
| Phone | Must be a real number for its country (Google's libphonenumber: lengths and prefixes); without a code it is Tunisian; `00` = `+`; no letters; stored as E.164 |
| E-mail | local part ≤ 64 (letters, digits, `.!#$%&'*+/=?^_`{\|}~-`, no leading, trailing or double dot); domain labels ≤ 63 (no leading/trailing hyphen), alphabetic or punycode top-level domain; ≤ 254 in total; stored lower case, international domains in ASCII (IDNA) |
| Country | One of the 245 ISO 3166-1 codes known to libphonenumber; typed as a name in English, French or Arabic (suggested by a `<datalist>`) or as the code |
| Room number | 1–10 characters `A-Z 0-9 -`, starting with a letter or digit, unique |
| Capacity | 1–10 guests; occupants per room ≤ capacity (BR7) |
| Amounts | `123`, `123.5`, `123,500` (≤ 3 decimals, ≤ 9 integer digits); stored as integer millimes; rates ≤ 100,000 DT; payments ≤ 1,000,000 DT; never negative |
| Stay | departure after arrival (BR4), ≤ 60 nights, 1–10 rooms, arrival not in the past for new bookings |
| Maintenance / rate period | ≤ 90 / ≤ 366 nights, no overlap |
| Extras | name 1–60, price > 0 and ≤ 10,000 DT, quantity 1–99 |
| Reasons, references, notes | ≤ 200 / ≤ 60 / ≤ 500 characters |
| Report range | ≤ 731 nights (W9) |
| Statuses, roles, themes, languages, report tables, sort columns | fixed allow-lists |

## Brute force and lockout abuse

* **Per account:** after 5 wrong passwords (or second-factor codes) the
  account is locked for 15 minutes, then 30, 60… up to 24 hours. A correct
  password does not help while locked, and attempts during a lock do not
  extend it.
* **Per address:** 20 failed sign-ins in 15 minutes from one address are
  refused before any password check; the JSON API allows 10 wrong tokens a
  minute per address.
* **Malicious lockout:** someone who knows a username can lock that account.
  The impact is limited because the lock is temporary, every lock is audited
  (`auth.account_locked`), another manager can unlock at once (Staff →
  Unlock), and the last manager can use `hotel reset-password` on the
  server. Usernames are never revealed by error messages (same message and
  same timing for unknown accounts).

## Dependency updates

* **Detection:** `pip-audit` runs on every CI build (a vulnerable dependency
  fails the build) and Dependabot checks pip packages, GitHub Actions and
  the Docker base images every week.
* **Time frames:** critical or high severity, fixed (or the component
  removed) within **7 days**; medium within **30 days**; low and routine
  updates within **90 days**, batched. A known vulnerability is never
  shipped in a release.
* **How:** update the range in `pyproject.toml` if needed, regenerate the lock
  files with hashes, let CI run on Linux and Windows, merge.
