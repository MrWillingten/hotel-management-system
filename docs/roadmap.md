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

**Learn first:** Flask app factory and blueprints · Jinja templates · `sqlite3` and transactions · `@dataclass(frozen=True)` · decorators · context managers · password hashing.

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

### Sprint 2 – Rooms, guests, staff, audit ✅

**Learn first:** ABCs and the repository pattern · SQL `LIKE … ESCAPE` · `hashlib` · Unicode normalisation · the SQLite backup API.

| ID | Story | PR | Status |
|---|---|---|---|
| 2.6 | Tamper-evident audit log | #18 | ✅ |
| 2.7 | Staff account management | #19 | ✅ |
| 2.1 / 2.2 | Room categories, rooms, maintenance | #20 | ✅ |
| 2.3 / 2.4 / 2.5 / 2.9 | Guests, search, masked documents, flags | #21 | ✅ |
| 2.8 | Backups and restore | #22 | ✅ |
| 2.10 | Demo data, lock files, release | #23 | ✅ |

Retrospective: the secret scanner and CI each caught a real problem before
merge (an inline test password; a template hidden by a too-broad
`.gitignore` pattern). Lesson: anchor ignore patterns, and never chain a
commit with a push.

### Sprint 3 – Reservations ✅

**Learn first:** transaction isolation and `BEGIN IMMEDIATE` · `UNIQUE` constraints as guards · threads in tests · optimistic locking.

| ID | Story | PR | Status |
|---|---|---|---|
| 3.1 / 3.2 / 3.3 / 3.7 | Availability, booking, alternatives, concurrency | #33 | ✅ |
| 3.5 / 3.6 | Change and cancel (BR11) | #34 | ✅ |
| 3.4 / 3.8 / 3.9 | Grid, room-change guards, guest history | #35 | ✅ |

Retrospective: the riskiest sprint finished on time. A test exposed a real
availability bug (maintenance nights skipped) that the database's
`room_night` key had silently contained; the layered defence (Python
check + transaction + key) did exactly what ADR 0004 promised. Lesson:
test every query with *both* kinds of blocked night.

### Sprint 4 – Front desk and billing ✅

**Learn first:** Strategy pattern and polymorphism · `Decimal.quantize` and rounding modes · print CSS.

| ID | Story | PR | Status |
|---|---|---|---|
| 4.2 / 4.9 / 4.1 | Check-in, no-show, housekeeping, front-desk dashboard | #46 | ✅ |
| 4.3 / 4.8 | Extra services and charges, hotel settings, tax rules | #47 | ✅ |
| 4.4 / 4.5 / 4.6 | Bill preview, discounts, payments and refunds | #48 | ✅ |
| 4.7 / 4.1 / 4.9 | Check-out, invoices, print styles, balances and maintenance on the dashboard, housekeeping dirty → cleaned → inspected, `hotel reset-password` | #49 | ✅ |

Retrospective: making the bill one pure function (`build_bill`) paid off at
once: the preview, the desk balance, the check-out preview and the invoice
can never disagree, and the brief's §4.7 example became a two-line test.
Two lessons: a nested Unit of Work would wait on its own write lock, so
settings are read through the caller's transaction (`load_settings(uow)`);
and Jinja's `gettext` always applies `%` formatting, so a literal percent
sign in a translatable string must be written `%%`.

### Sprint 5 – Reports, operations, languages (7 – 20 Dec) → code complete

**Learn first:** SQL aggregation (`GROUP BY`, date ranges) · generating SVG · `csv` ·
gettext and Babel catalogues.

| ID | Story | Acceptance criteria |
|---|---|---|
| 5.1 | As a manager, I consult every §4.8 statistic | Reservation count, occupancy rate (decision H), top categories, accommodation, service and tax revenue, cancellations, outstanding balances, availability, for any date range. Range capped at 2 years (threat W9). |
| 5.2 | As a manager, I see charts | Server-generated SVG charts (no JavaScript) that follow the theme and work in both themes and in RTL. |
| 5.3 | As a manager, I export reports to CSV | Formula injection escaped (test, threat I5). ID numbers excluded. |
| 5.4 | As the hotel, the night audit closes each day | Marks no-shows, flags guests who should have left, saves a daily snapshot. Safe to run twice. |
| 5.5 | As a French- or Arabic-speaking user, the interface speaks my language | FR and AR catalogues complete (test). Locale-aware money input. Western digits in Arabic, `<bdi>` around codes and amounts. **The student reviews the translations.** |
| 5.6 | As a manager, I set seasonal and weekend rates | Rate periods per category. Locked prices on existing reservations unaffected (only `ReservationService._rate_for` changes). |
| 5.7 | As a manager, I anonymise old guests | Personal data replaced, invoices keep their own copy of the name, action audited. |
| 5.8 | Seed v2 | Several months of realistic history, so the reports and charts look alive in the demo. |

Decisions taken with the student before the sprint (11 Oct): revenue counts
**when invoiced**, with cash received shown separately · the night audit runs
from a button, a command and a catch-up at start-up · weekend nights default to
**Saturday and Sunday nights** (a setting) · anonymisation after **24 months**
without a stay (a setting). Issues #50 (5.0, a link from the room form to the
categories) to #58.

### Sprint 6 – Stretch, freeze, delivery (21 Dec – 3 Jan)

| When | Work |
|---|---|
| 21 – 26 Dec | **Stretch, in this order:** TOTP 2FA for managers → Docker image → read-only JSON API → Windows executable → moving a guest between rooms |
| **27 Dec** | **Feature freeze** (moved earlier if the deadline is earlier). After this, bug fixes only. |
| 27 Dec – 2 Jan | Manual checklist on real Windows plus three browsers · security self-assessment against OWASP ASVS Level 1 · test evidence table · report final assembly (Times New Roman 12 pt, 1.5 spacing, numbered figures) · screenshots in both themes and three languages · demo script plus **two full rehearsals** |
| 3 Jan | `v1.0.0` tagged, release notes, PDF of the report |

**The report is written along the way:** each sprint's Definition of Done
includes updating its report section; leaving 40–50 pages for the last week
would fail.

## Cut order if late

1. Moving a guest between rooms · 2. Windows executable · 3. Docker ·
4. JSON API · 5. TOTP · 6. Seasonal rates · 7. Anonymisation · 8. Charts ·
9. Arabic translation (layout stays RTL-ready) · 10. Housekeeping.
**Never cut:** the brief's requirements, critical/high security controls, tests,
backups, audit chain, report.

## Top risks

| Risk | Mitigation |
|---|---|
| Sprint 3 (reservations) slips | Hardest logic scheduled early; checkpoint at the end of Sprint 3; Sprint 6 acts as a buffer (passed: Sprint 3 finished on time) |
| Exams or the deadline land earlier than expected | Code complete on 20 Dec; ask the professor for the exact dates |
| Can't explain AI-written code | The "explain every line" item in the Definition of Done; "Learn first" per sprint |
| Windows-only bugs found late | Windows CI from day 1; one real Windows test per sprint, not only at the end |
| Burnout | A sustainable ~25 h/week plan; stretch goals are optional by design |

The cut list above is applied **at the end of a sprint**, never in a panic in December.

## Git workflow

* `main` is always green and protected: changes arrive through pull requests with passing CI.
* One short-lived branch per story: `feat/2.3-guest-registration`, `fix/...`, `docs/...`.
* Squash-merge; the PR closes its issue (`Closes #12`).
* GitHub Issues per story (acceptance criteria as a checklist), a Milestone per sprint,
  a PR template with the Definition of Done as a self-review checklist.
* ADRs in `docs/adr/`: one short page per important decision (they become the
  report's "justification of design choices").
* [Conventional Commits](https://www.conventionalcommits.org/): `feat`, `fix`, `test`, `docs`, `refactor`, `perf`, `ci`, `chore`, `sec`.
* An annotated tag and GitHub release per sprint; `CHANGELOG.md` follows *Keep a Changelog*.
* Sprint 1 was built before the GitHub repository existed, so its stories were
  committed directly on `main`; from Sprint 2 every story goes through a PR.
* Dependencies are pinned with hashes in `requirements.lock` /
  `requirements-dev.lock` (generated with `uv pip compile --universal
  --generate-hashes`); CI installs from them with `--require-hashes`.

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

**Sprint**: all stories done → tag and release → demo script for the professor's
check-in → three-point retrospective (what went well, what didn't, what to
change), which feeds the report's "difficulties and solutions" section.
