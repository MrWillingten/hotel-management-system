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
| A5 | 🟠 | A route forgets its role check | Deny by default; every view declares `@public`, `@login_required` or `@roles_required`; a test walks every route; services re-check roles | ✅ S1 (services ⏳ S2+) |
| A6 | 🟠 | Receptionist grants own discounts or large refunds | Discounts and refunds manager-only (role re-checked in the service), capped, reason required, audited | ✅ S4 |
| A7 | 🟡 | Session fixation | New token at every login, previous one destroyed | ✅ S1 |
| A8 | 🟡 | Last manager deactivated or demoted; manager deactivating self | Refused | ✅ S2 |
| A9 | 🟡 | Manager knows a reset password | `must_change_password` blocks every page until changed; reset ends sessions | ✅ S2 |
| A10 | 🟡 | Missing traceability | Hash-chained, append-only audit log (triggers + SHA-256 chain); `hotel audit verify`; manager viewer | ✅ S2 |
| A11 | ⚪ | TOTP replay | The last accepted time step is stored; a code of that step or an earlier one is refused (RFC 6238 §5.2) | ✅ S6 |
| A12 | 🟠 | A stolen manager password alone opens every manager page | TOTP second factor (RFC 6238, standard library, RFC test vectors); required for managers after a 7-day grace period (pages blocked until enrolled); the session opens only after the code (hashed 5-minute challenge, 5 tries); wrong codes count toward the account lockout (A3); 10 one-time recovery codes stored as SHA-256; enrolment confirmed by one code; `hotel reset-totp` for a lost phone; every step audited | ✅ S6 |
| A13 | ⚪ | The TOTP secret is readable in a stolen database | Accepted: the secret must be readable to compute codes. It is useless without the scrypt-protected password, and a stolen database already exposes everything else; backups are protected like the database | ✅ S6 (accepted) |

## Web

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| W1 | 🔴 | Werkzeug debugger in production (remote code execution) | Production is the default; Waitress never enables debug; start-up refuses `FLASK_DEBUG` in production | ✅ S1 |
| W2 | 🔴 | Secret key in Git or weak | Generated on first start in `instance/` (git-ignored, mode 0600); weak keys refused | ✅ S1 |
| W3 | 🟠 | Passwords in clear text on the LAN | Binds to 127.0.0.1 by default; LAN mode documented with Caddy HTTPS; warning printed | ✅ S1 (docs) |
| W4 | 🟠 | Missing security headers | CSP (`default-src 'self'`, no inline scripts or styles, `frame-ancestors 'none'`), `nosniff`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, COOP, HSTS behind HTTPS | ✅ S1 |
| W5 | 🟠 | Back button shows guest data after logout | `Cache-Control: no-store` on every page | ✅ S1 |
| W6 | 🟡 | IDOR | Role per object type; services check | ⏳ S2+ |
| W7 | 🟡 | Stack traces leak | Generic 500 page with incident id | ✅ S1 |
| W8 | 🟡 | Vulnerable dependencies | pip-audit in CI, Dependabot | ✅ S1 |
| W9 | ⚪ | Expensive report ranges | 2-year cap (731 nights), tested | ✅ S5 |
| W10 | ⚪ | File uploads | None by design | ✅ |

## Input validation and injection

| ID | Sev | Risk | Control | Status |
|---|---|---|---|---|
| I1 | 🔴 | SQL injection | Every query uses `?` parameters; sorting through whitelists; `LIKE` escaping; bandit in CI; injection strings in search tests | ✅ S2 |
| I2 | 🟠 | XSS | Jinja autoescaping, no `|safe` on user data, strict CSP; test with a `<script>` name | ✅ S1 |
| I3 | 🟠 | CSRF | Flask-WTF on every POST; logout and preferences are POST; `SameSite=Lax` | ✅ S1 |
| I4 | 🟠 | Trusting hidden form fields | Server recomputes prices; whitelisted preference values | ✅ S1 (prices ⏳ S3) |
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
| C2 | 🟠 | Lost updates | `version` column, `StaleDataError` | ✅ S1 (users) |
| C3 | 🟠 | Double submit | One-time form tokens (owner-bound, 8 h, hashed) on booking, change, cancel, charges, payments and refunds; version checks on check-in/out | ✅ S3–S4 |

## Accepted limitations

* The database file and backups are not encrypted at rest: protect them with
  OS permissions and full-disk encryption (BitLocker / LUKS).
* Without a TLS reverse proxy, LAN use exposes passwords on the network.
* The common-password list only contains passwords of 12+ characters from a
  public list; it cannot catch every predictable password.
