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
- Sprints 1–3 → v0.1.0, v0.2.0, v0.3.0. Details: `CHANGELOG.md`.

### Next: Sprint 4 – Front desk and billing (23 Nov – 6 Dec)
Stories in `docs/roadmap.md` (4.1–4.9): dashboard figures, check-in /
no-show, service catalogue + charges, bill preview (night-by-night,
discounts as Strategy classes, tax rules: percentage + per-adult-night,
prices tax-exclusive, half-up per line), discounts (manager, capped 30 %),
payments/refunds, check-out → immutable gap-free invoices + print CSS,
settings & tax-rule screens, housekeeping status. Golden test from the
brief §4.7 (3 × 150 + 80 services − 100 deposit).
Then Sprint 5 (reports, charts, CSV, night audit, seasonal rates,
anonymisation, translation review) and Sprint 6 (TOTP, Docker, JSON API,
Windows exe, room moves, freeze, report, demo).

### Known open issues / limitations (not bugs yet fixed)
- French and Arabic texts are drafts → native-speaker review before demo.
- Tests set `CHECKED_IN` directly (`_check_in` helper in
  `tests/integration/test_change_and_cancel.py`) until Sprint 4 adds check-in.
- A cancelled reservation shows an accommodation total of 0 (its nights are
  released); the fee is stored. Revisit when invoices exist (Sprint 4).
- Shortening a stay within 48 h charges no fee (documented decision).
- Phone numbers are stored normalised and shown unformatted.
- Daily automatic backup runs at start-up only; long-running servers need a
  scheduled `hotel backup` (documented in `docs/deployment.md`).
- Dashboard still shows placeholders + roadmap (real figures in Sprint 4).

### Bugs found and fixed (lessons)
- `.gitignore` `backups/` hid `templates/backups/` → anchor root patterns.
- Availability skipped maintenance nights (`IS NOT NULL` with no exclusion);
  DB key contained it → test both kinds of blocked night.
- Hidden grid labels widened RTL pages → `position: relative` on cells.
- Leaked SQLite handle on corrupt files → close in `connect()` on error.
