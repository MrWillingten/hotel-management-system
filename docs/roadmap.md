# Roadmap and way of working

Solo project, two-week sprints, professor check-in at the end of each sprint.
Code complete on **20 December 2026**; the last sprint is for stretch goals,
hardening, the report and the demo.

## Sprints

| Sprint | Dates | Theme | Tag |
|---|---|---|---|
| 1 | 12 – 25 Oct | Foundations: repo, CI, sign-in, themes, languages | `v0.1.0` |
| 2 | 26 Oct – 8 Nov | Rooms, guests, staff, audit log, backups | `v0.2.0` |
| 3 | 9 – 22 Nov | Reservations and availability (riskiest sprint) | `v0.3.0` |
| 4 | 23 Nov – 6 Dec | Front desk and billing | `v0.4.0` |
| 5 | 7 – 20 Dec | Reports, operations, French and Arabic → code complete | `v0.9.0` |
| 6 | 21 Dec – 3 Jan | Stretch → feature freeze (27 Dec) → hardening, report, demo | `v1.0.0` |

### Sprint 1 – Foundations ✅

| ID | Story | Status |
|---|---|---|
| 1.1 | Repository, CI on Ubuntu and Windows, linters, security scanners | ✅ |
| 1.2 | First manager created from the command line, no default password | ✅ |
| 1.3 | Secure sign-in and sign-out (server sessions, lockout, throttling) | ✅ |
| 1.4 | Deny-by-default access policy and security headers | ✅ |
| 1.5 | Cognac theme: light, dark, system; responsive layout | ✅ |
| 1.6 | Language switcher (EN, FR, AR with right-to-left) | ✅ |
| 1.7 | Domain foundations: `Money`, `StayPeriod`, `Clock`, error codes | ✅ |
| 1.8 | Persistence foundations: PRAGMAs, migrations, Unit of Work | ✅ |

### Sprint 2 – Rooms, guests, staff, audit

Room categories and rooms · maintenance ("reopens on") · guests with duplicate
detection · guest search, pagination and sorting · masked ID numbers · hash-chained
audit log and viewer · staff management (create, deactivate, reset, change own
password, last-manager protection) · backup / restore · VIP and "do not rent"
flags · demo seed v1 · pinned dependency lock file.

### Sprint 3 – Reservations

Availability search · multi-room booking with per-night locked prices ·
conflict suggestions · availability grid · modification with optimistic locking ·
cancellation fee (47:59 / 48:00 / 48:01 tests) · two-thread race test and
one-time form tokens · room edits that would break bookings are refused ·
guest reservation history.

### Sprint 4 – Front desk and billing

Dashboard · check-in / no-show · service catalogue and charges · bill preview with
discounts and taxes (golden test from the brief) · payments and refunds · check-out
and immutable, gap-free invoices with print styles · settings and tax rules ·
housekeeping status.

### Sprint 5 – Reports, operations, languages

All §4.8 statistics · SVG charts · CSV export · night audit · full French and
Arabic review · seasonal rates · guest anonymisation · seed v2.

### Sprint 6 – Stretch, freeze, delivery

Stretch order: TOTP for managers → Docker image → read-only JSON API → Windows
executable → moving a guest between rooms. Then freeze, manual checks on real
Windows and three browsers, OWASP ASVS level 1 self-assessment, report, demo.

## Cut order if late

1. Moving a guest between rooms · 2. Windows executable · 3. Docker ·
4. JSON API · 5. TOTP · 6. Seasonal rates · 7. Anonymisation · 8. Charts ·
9. Arabic translation (layout stays RTL-ready) · 10. Housekeeping.
**Never cut:** the brief's requirements, critical/high security controls, tests,
backups, audit chain, report.

## Git workflow

* `main` is always green and protected: changes arrive through pull requests with passing CI.
* One short-lived branch per story: `feat/2.3-guest-registration`, `fix/...`, `docs/...`.
* Squash-merge; the PR closes its issue (`Closes #12`).
* [Conventional Commits](https://www.conventionalcommits.org/): `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `ci`, `chore`, `sec`.
* An annotated tag and GitHub release per sprint; `CHANGELOG.md` follows *Keep a Changelog*.
* Sprint 1 was built before the GitHub repository existed, so its stories were
  committed directly on `main`; from Sprint 2 every story goes through a PR.

## Definition of Done

**Story**
- [ ] Acceptance criteria met; related brief scenarios have a named test
- [ ] Tests written; CI green on Ubuntu and Windows; coverage did not drop
- [ ] ruff, bandit and pip-audit clean
- [ ] New routes: declared policy, CSRF, POST for changes
- [ ] All user-visible text translatable; works in both themes, < 900 px and RTL
- [ ] Sensitive actions audited; no personal data in logs
- [ ] Docs / ADR / report notes updated
- [ ] **I can explain every changed line without notes**
- [ ] Merged through a PR; issue closed

**Sprint**: all stories done → tag and release → demo script → three-point retrospective.
