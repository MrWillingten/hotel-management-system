# CLAUDE.md – working notes for this project

Read this first in every session (and again after a context compaction).
Two parts: **stable rules** (never delete) and **living status** (trim as
work finishes: move details to `CHANGELOG.md` / `docs/roadmap.md`, keep a
one-line pointer here).

---

## Part 1 – Stable rules

### The project
- Semester project, *Python Programming*, Engineering Cybersecurity 1st year.
  Brief: **Project 3 – Hotel Reservation and Management System** (PDF outside
  the repo: `../Python_Semester_Project_Student_Reference.docx.pdf`).
- Solo student (GitHub **MrWillingten**). Repo:
  https://github.com/MrWillingten/hotel-management-system (public).
- Web app (Flask) instead of the minimum terminal app. Professor's rule:
  *anything not studied in class is allowed, but she will ask about it;
  explaining it right is a bonus, failing is a minus.* → keep the stack
  small and every line explainable; disclose AI assistance (README does).
- Scope decision: **everything** – must-haves, nice-to-haves and stretch
  goals, plus English/French/Arabic (RTL). Cut order exists in
  `docs/roadmap.md` but is only used if the calendar forces it.
- Deadline ≈ end of Dec 2026 / early Jan 2027. Code complete target
  **20 Dec**; Sprint 6 = stretch, freeze (27 Dec), report (40–50 pages,
  Times New Roman 12, 1.5 spacing), demo.

### Where the truth lives
| Topic | File |
|---|---|
| Business rules BR1–26, decisions Q1–Q5/A–H (taxes in scope) | `docs/requirements.md` |
| Layers, modules, error handling | `docs/architecture.md`, `docs/adr/` |
| ERD + schema (✅ = exists) | `docs/data-model.md` |
| Threat review and control status | `docs/security.md` |
| Sprints, stories, DoD, Git workflow, retrospectives | `docs/roadmap.md` |
| What each release contains | `CHANGELOG.md` |

### Architecture in one breath
`web/ (Flask) → services/ → domain/ ← persistence/ (SQLite)`; `cli.py` uses the
same services. Domain is pure Python (test enforces imports). Composition
root: `bootstrap.build_services()`. Every write = one `UnitOfWork`
(`BEGIN IMMEDIATE`). Errors carry codes → translated in `web/messages.py`.
Money = integer millimes (`Money`), stays = half-open `StayPeriod`, time from
an injected `Clock` (Africa/Tunis). `room_night` PK(room_id, night) makes
double booking impossible in the DB (ADR 0004). Audit log is hash-chained.

### Commands (venv: `.venv`, Python 3.14 locally; CI 3.11 + 3.13, Ubuntu + Windows)
```
.venv/bin/python -m pytest -q --cov                 # 90 % floor
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/bandit -c pyproject.toml -r src -q
.venv/bin/python scripts/i18n_sync.py [new.json]    # after changing UI text
HOTEL_DATA_DIR=/tmp/x .venv/bin/python -m hotel seed --demo   # demo data
```
Preview server: `.claude/launch.json` ("hotel", port 8765, data dir in the
session scratchpad). Re-run `uv pip install -e .` after a version bump.

### Workflow (follow exactly)
1. Milestone + one issue per story on GitHub before coding a sprint.
2. One branch per story group (`feat/<id>-name`), Conventional Commits,
   PR with `Closes #n`, wait for the 5 CI checks, **squash-merge**.
3. After a squash merge, rebase the next branch with
   `git rebase --onto origin/main <old-base-commit>`.
4. Never chain `git commit` and `git push` in one command (a blocked commit
   would still push). gitleaks blocks inline passwords in tests → use
   module constants (`TEMP = "..."`).
5. Every user-visible string translatable; run `scripts/i18n_sync.py`;
   avoid plural nouns in strings ("Nights: %(n)s", not "%(n)s nights").
6. SQL: only `?` parameters; dynamic fragments via fixed templates
   (`_TEMPLATE.format(where=...)`), whitelisted ORDER BY, `escape_like`.
7. End of sprint: docs + CHANGELOG + version bump in `pyproject.toml`,
   lock files if deps changed (`uv pip compile ... --universal
   --generate-hashes`), annotated tag `vX.Y.0`, GitHub release, close milestone.
8. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`;
   PR bodies end with the Claude Code line.
9. Definition of Done includes: *the student can explain every changed
   line* – explain key decisions in the summary to the user.
10. Never enter passwords/sudo for the user; ask them to run such commands.

### Style
Comments explain *why*, briefly, in the same density as existing code.
Templates: `macros/forms.html` (field, select, textarea, checkbox,
form_errors, csrf), logical CSS properties only, tokens in `app.css`,
icons in `macros/icons.html`. Tests: unit (domain), integration (services +
SQLite), e2e (Flask client). Shared fixtures `hotel`, `signed_in` in
`tests/conftest.py`.

---

## Part 2 – Living status (trim as it changes)

### Done
- Phases 1–5 (analysis, architecture, growth, security review, agile plan).
- Sprints 1–5 → v0.1.0 … v0.9.0 (code complete). Details: `CHANGELOG.md`, `docs/roadmap.md`.
- Sprint 5 map: reports `domain/reports.py` + `repositories/reports.py` + `services/reports.py`;
  charts `web/charts.py` + `macros/charts.html`; CSV `web/csv_export.py`; night audit
  `domain|services/night_audit.py` (catch-up in `cli.cmd_run`); prices `domain/pricing.py`;
  anonymisation `Guest.anonymise` + `GuestService.anonymise`; demo replay `demo.py`
  (`history_days`). Migrations 0012–0014.
- Accounts: passwords are only stored as scrypt hashes (unrecoverable). First
  manager: `hotel create-manager`; staff: Staff page (temporary password);
  forgotten password (even the last manager): `hotel reset-password USERNAME`.
- Sprint 4 map (to find things fast): front desk `services/front_desk.py`;
  check-in/no-show in `services/reservations.py`; extras `domain|services/extras.py`
  (named "extras" to avoid clashing with the service layer); settings
  `domain/settings.py` + `services/hotel_settings.load_settings(uow)`; taxes
  `domain/taxes.py`; bill `domain/billing.build_bill()` + `services/billing.bill_for(uow, r)`;
  invoices `domain|services/invoices.py` (`issue_invoice` also used by cancel/no-show).
  Migrations 0007–0010. Web: blueprints `billing`, `extras`, `hotel_settings`, `invoices`.

### Next: Sprint 6 – Stretch, freeze, delivery (21 Dec – 3 Jan) → v1.0.0
Plan in `docs/roadmap.md` (Sprint 6 table). Stretch order: TOTP 2FA for
managers → Docker image → read-only JSON API → Windows executable → moving
a guest between rooms. Feature freeze 27 Dec, then manual Windows + three
browsers checklist, OWASP ASVS L1 self-assessment, test evidence table,
report (40–50 pages), screenshots in both themes and three languages,
demo script and two rehearsals. As agreed: draft the Sprint 6 stories and
show them to the student **before** creating issues.
Sprint 5 translation review done by the assistant at the student's request
(34 corrections, see docs/translations.md); a native-speaker read before the
demo is still advised.

### Known open issues / limitations (not bugs yet fixed)
- French and Arabic texts reviewed once (AI) → a native-speaker read before the
  demo with `scripts/i18n_review.py`.
- Shortening a stay within 48 h charges no fee; early departure charges no
  fee either (decision F, documented).
- Check-out is allowed with a balance due (shown under "Unpaid after
  departure"); there are no credit notes: corrections after an invoice are
  payments/refunds on the reservation.
- Demo tax rates (VAT 7 %, 19 % on services, 3 DT/adult/night) are examples
  to verify against Tunisian regulations.
- Phone numbers are stored normalised and shown unformatted.
- Daily automatic backup runs at start-up only; long-running servers need a
  scheduled `hotel backup` (documented in `docs/deployment.md`).
- No JavaScript at all (CSP): printing is the browser's Ctrl+P.

### Bugs found and fixed (lessons)
- `.gitignore` `backups/` hid `templates/backups/` → anchor root patterns.
- Availability skipped maintenance nights (`IS NOT NULL` with no exclusion);
  DB key contained it → test both kinds of blocked night.
- Hidden grid labels widened RTL pages → `position: relative` on cells.
- Leaked SQLite handle on corrupt files → close in `connect()` on error.
- Jinja `_()` always %-formats: a literal `%` in a translatable string must be `%%`.
- A nested Unit of Work inside another waits on its own write lock → pass
  the open `uow` to helpers (`load_settings(uow)`, `bill_for(uow, r)`).
- Blueprint module named `settings` was shadowed by `create_app(settings)` → `hotel_settings`.
- Amounts/percentages render with a non-breaking space (`\u00a0`) → tests must use it;
  in templates amounts are also wrapped in `<bdi>`.
- Chained commit+push happened again (formatter hook changed a file) → PR showed
  no change; always commit, check, then push separately.
- Demo replay clock jumped past "now" when started in the afternoon → start at
  07:00 on day one and stop the evening before today.
