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
| UML (2 use case, 3 class diagrams) | `docs/diagrams/*.drawio` (student's choice: editable at app.diagrams.net, export PDF for the report; update classes by hand after domain changes) |
| Every page/button per role; Help page content | `docs/user-guide.md`, `web/help.py` |

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

### Next: Sprint 6 – Stretch, freeze, delivery (starts now, freeze 27 Dec) → v1.0.0
**Stories 6.1–6.9 are approved and written in full in `docs/roadmap.md`**
(Sprint 6 table + decisions). Read it before starting. To do, in order:
1. ✅ Milestone "Sprint 6" (#5) + issues #67–#75 (6.1 = #67 … 6.9 = #75).
2. ✅ 6.1 TOTP (PR #76): `domain/totp.py`, `services/two_factor.py`, two-step
   login in `services/auth.py` (`login` → challenge → `complete_login`), gate in
   `web/security.py`, migration 0015, ADR 0006. Test helpers in conftest:
   `enrol_two_factor`, `login_with_code` (advance the clock 30 s after enrolling).
   Tests that jump > 7 days with a manager must enrol (grace gate).
3. ✅ 6.2 Docker (PR #77): `Dockerfile`, `deploy/compose.yaml` + `Caddyfile`, public
   `/health`, CI job "Docker image" (no Docker locally → CI is the test).
   ✅ 6.3 JSON API (PR #78): `web/blueprints/api.py`, `@api_token_required` in
   `web/security.py` (cookie refused, per-app `RateLimiter`), `services/api_tokens.py`,
   Account → API tokens, `docs/api.md`, migration 0016.
   ✅ 6.4 Windows exe (PR #80): `packaging/windows/` (launcher, spec, README),
   `requirements-build.lock` (extra `build`), CI job "Windows executable" → artifact.
   ✅ 6.5 room move (PR #81): `Reservation.move_room`, `ReservationService.move_room/move_candidates`,
   `reservation_room.moved_out_on` (migration 0017): use `reservation.current_rooms`
   for anything about *now* (occupancy, housekeeping, edits); `rooms` keeps history.
   Dependabot ignores Python minor bumps of the image (tested versions only).
4. ✅ 6.6 hardening docs (PR after #81): `docs/asvs.md` (ASVS 5.0 L1, from the
   official CSV), `docs/test-evidence.md`, `docs/manual-checks.md` (Firefox/Edge
   and real-Windows columns are the **student's**; issue #72 stays open until
   then), `tests/unit/test_docs.py` checks cited tests exist. Cookies:
   `web/context.cookie_name()` adds `__Host-` behind HTTPS.
   ✅ Frontend polish 6.10–6.14 (student's requests, 11 Oct): 6.10 user guide
   (`docs/user-guide.md`) + Help page (`web/help.py`); 6.11 scrollbar; 6.12 sign-in
   (`partials/auth_hero.html`, Great Vibes, CSS/SVG animation, reduced motion);
   6.13 invoice sheet (`.invoice-doc` redefines tokens locally = always light;
   `@page` A4); 6.14 walk-through (`web/tour.py`, `blueprints/welcome.py`,
   `domain|services/onboarding.py`, checklist ticks from `audit.actions_of`,
   migration 0018). PRs #88 (6.10–6.12) and the 6.13–6.14 PR.
   ✅ Corrections 6.15–6.17 (student, 18 Oct; roadmap "Corrections requested"):
   6.15 guest checks (`domain/guests.py`: passport ICAO, `phonenumberslite`
   E.164 + `phone` filter, e-mail parts, `COUNTRY_CODES`; `web/countries.py`
   datalist names EN/FR/AR → ISO) PR #93; 6.16 tax `payers` + `home_country`
   setting + `tax_exemption` (`taxes_for_stay` in `services/billing.applicable_taxes`)
   and 6.17 delete-or-archive (`domain/removal.py`, `archived_at` on 5 tables,
   `web/removal.confirm_removal`, macros `archive.html` imported *with context*)
   PR #94. Migrations up to 0020.
   ✅ UML diagrams (19 Oct, PR #95: squash-merge once CI is green): 5 draw.io files in
   `docs/diagrams/` (student asked for files to upload; ERDPlus has no UML, draw.io chosen).
   Graphviz versions replaced. Class content was read from code with `ast`, laid out by
   Graphviz (splines=polyline → exact draw.io waypoints); use cases on a 2-column grid so
   no line crosses an ellipse. Converter scripts were one-off (not in the repo).
   **NEXT:** student tries the UI and checks the diagrams; then 6.7 report
   (LaTeX/Overleaf in `report/`, PDFs exported from the draw.io files). Freeze 27 Dec.
   Running the app: `.venv/bin/python -m hotel run` (the student's `sh` kept
   /usr/bin/python after activation).
5. 6.7 report: **English, LaTeX for Overleaf** in `report/`. The assistant
   drafts all technical chapters; **the student writes the General
   Introduction, personal retrospectives, lessons learned, difficulties and
   the conclusion** — leave clearly marked placeholders for those, never
   write them. Declare AI assistance.
6. 6.8 demo script/screenshots/rehearsal checklist, 6.9 v1.0.0.

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
- Phone numbers stored before 6.15 may lack +216 (shown formatted anyway; duplicate
  detection compares the stored form).
- Daily automatic backup runs at start-up only; long-running servers need a
  scheduled `hotel backup` (documented in `docs/deployment.md`).
- No JavaScript at all (CSP): printing is the browser's Ctrl+P.

### Bugs found and fixed (lessons)
- Regenerating `requirements-dev.lock` with a newer uv dropped `typing-extensions`
  (<3.13 marker) → when adding a dependency, regenerate `requirements.lock` but
  only insert the new block into the dev lock; check `git diff` of both.
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
