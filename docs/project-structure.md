# Project structure: every folder and file

A guided tour of the repository: what each folder is for and what each file
does. Read top to bottom, it follows the path of a request:
**web → services → domain ← persistence**.

```
Project/
├── src/hotel/            the application (Python package "hotel")
│   ├── domain/           business concepts and rules (pure Python)
│   ├── services/         use cases: role checks, transactions, audit
│   ├── persistence/      SQLite: connection, migrations, repositories
│   ├── web/              Flask: pages, forms, security, templates, CSS
│   ├── translations/     French and Arabic texts
│   └── data/             data files shipped with the app
├── tests/                unit, integration and end-to-end tests
├── docs/                 analysis, design, security, diagrams, guides
├── scripts/              developer tools (translations)
├── packaging/windows/    Windows .exe build
├── deploy/               Docker Compose + HTTPS proxy example
├── .github/              CI pipeline and GitHub templates
└── (root files)          configuration, dependencies, licence
```

---

## 1. Root files

| File | Purpose |
|---|---|
| `README.md` | Front page: what the system does, how to install, run and test it, links to all documents |
| `CHANGELOG.md` | What each release (v0.1.0 … v0.9.0, …) added or fixed |
| `CLAUDE.md` | Working notes for the AI assistant (rules, status); AI assistance is declared in the README |
| `LICENSE` | MIT licence |
| `pyproject.toml` | Project definition: name, version, dependencies, the `hotel` command, and the settings of pytest, coverage, Ruff (linter) and Bandit (security scanner) |
| `requirements.lock` | Exact versions (with hashes) of the runtime dependencies, so every install is identical |
| `requirements-dev.lock` | Same, plus the development tools (pytest, Ruff, Bandit...) |
| `requirements-build.lock` | Same, plus PyInstaller for the Windows executable |
| `babel.cfg` | Tells Babel where to find translatable text (Python files and templates) |
| `Dockerfile` | Builds the Docker image: small, non-root user, data in a volume, health check |
| `.dockerignore` | Files kept out of the Docker image |
| `.gitignore` | Files Git must not track (virtual environment, databases, backups, caches) |
| `.gitattributes` | Line-ending rules so Windows and Linux checkouts behave the same |
| `.editorconfig` | Shared editor settings (indentation, UTF-8, final newline) |
| `.pre-commit-config.yaml` | Checks run before every commit: formatting, lint, secrets detection (gitleaks) |

## 2. `src/hotel/` – the application

| File | Purpose |
|---|---|
| `__init__.py` | Marks the package; reads the installed version |
| `__main__.py` | Makes `python -m hotel ...` work (calls the CLI) |
| `cli.py` | Command line: `run`, `init-db`, `create-manager`, `reset-password`, `reset-totp`, `night-audit`, `seed --demo`, `backup`, `restore`, `audit verify`, `version` |
| `bootstrap.py` | **Composition root**: the one place where database, repositories, services and clock are created and connected (`build_services()`); used by both the web app and the CLI |
| `config.py` | Reads settings from environment variables (data folder, port, HTTPS, debug); safe production defaults |
| `secret_key.py` | Creates the key that signs cookies and CSRF tokens, stored with owner-only file permissions |
| `demo.py` | Fills a database with fictional demo data, replaying months of activity (`hotel seed --demo`) |

### 2.1 `src/hotel/domain/` – business rules (no database, no web)

Pure Python classes and functions. A test (`tests/unit/test_architecture.py`)
fails if this folder ever imports Flask, SQLite or another layer.

| File | What it contains |
|---|---|
| `money.py` | `Money`: amounts in integer **millimes** (1 DT = 1000), so no floating-point rounding errors |
| `period.py` | `StayPeriod`: arrival/departure as a half-open range `[arrival, departure)`; overlap test used against double booking |
| `clock.py` | `Clock`, `SystemClock`, `FixedClock`: where "now" comes from (Africa/Tunis); tests use a fixed clock |
| `enums.py` | Closed sets of values: `Role`, `ReservationStatus`, `Housekeeping`, `PaymentMethod`, `IdDocType`... |
| `errors.py` | Exception hierarchy (`HotelError` → `ValidationError`, `NotFoundError`, `BusinessRuleViolation`, `ConflictError`, `PermissionDeniedError`...), each with a code translated by the web layer |
| `actor.py` | `Actor`: who performs an operation (a user or the system) and from which IP |
| `users.py` | `User`, `UserSession`, lockout policy (5 failures → 15 min) |
| `passwords.py` | Password rules: length, not a common password, not containing the username |
| `totp.py` | Two-factor codes (RFC 6238) computed with `hmac`/`hashlib` from the standard library |
| `api_tokens.py` | `ApiToken`: personal tokens for the read-only JSON API, stored as SHA-256 hashes |
| `rooms.py` | `RoomCategory`, `Room`, `MaintenancePeriod`, housekeeping states |
| `pricing.py` | Price of a room on a given night: base rate, seasonal rates, weekend surcharge |
| `guests.py` | `Guest`, `GuestDetails`; checks for passport, CIN, phone (E.164 via `phonenumbers`), e-mail, nationality; anonymisation |
| `reservations.py` | `Reservation`, `BookedRoom`, `RoomNight`; life cycle (booked → checked in → checked out / cancelled / no-show); cancellation policy; room move |
| `extras.py` | `Extra` (breakfast, transfer...) and `ServiceCharge` (an extra charged to a stay, price copied) |
| `taxes.py` | `TaxRule` with two strategies (`PercentTax`, `PerAdultNightTax`), who pays (everyone / foreigners / nationals), exemptions per stay |
| `billing.py` | `build_bill()`: pure function turning nights, extras, discounts, taxes and payments into a `Bill`; `Discount`, `Payment` |
| `invoices.py` | `Invoice`: a frozen copy of the bill at check-out; numbered without gaps |
| `settings.py` | `HotelSettings`: check-in/out times, cancellation fee and window, discount cap, home country... |
| `audit.py` | `AuditEntry`: each entry contains the hash of the previous one (hash chain), so editing or deleting history is detected |
| `night_audit.py` | Closing a business day: no-shows and the day's frozen figures |
| `reports.py` | Statistics: occupancy, average daily rate, RevPAR, revenue, cancellations |
| `paging.py` | `PageRequest`, `Page`: splitting long lists into pages |
| `removal.py` | Delete-or-archive rule: delete if never used, otherwise archive |
| `onboarding.py` | Walk-through for new accounts and the self-ticking checklist |

### 2.2 `src/hotel/services/` – use cases

One class per area. Each method: checks the role, opens **one transaction**
(Unit of Work), calls the domain, saves, writes the audit log.

| File | Use cases |
|---|---|
| `authorization.py` | Role checks: `require_role(actor, Role.MANAGER)`, `require_staff(actor)` |
| `auth.py` | Sign in (with lockout), two-step login with code, sessions, sign out |
| `passwords.py` | Password hashing with **scrypt** (`hashlib.scrypt`), never stored in clear |
| `two_factor.py` | Set up / disable two-factor, recovery codes |
| `users.py` | Staff accounts: create, edit, deactivate, temporary password, remove/archive |
| `api_tokens.py` | Create and revoke API tokens |
| `rooms.py` | Categories, rooms, maintenance, housekeeping, seasonal rates |
| `guests.py` | Register, search (accent-insensitive), edit, flag, reveal document (audited), anonymise |
| `reservations.py` | Availability, book, change, cancel, check in, no-show, move room |
| `front_desk.py` | The dashboard: arrivals, departures, in-house, rooms to clean |
| `extras.py` | Catalogue of extra services and charges to stays |
| `hotel_settings.py` | Settings and tax rules |
| `billing.py` | Bill, discounts, payments, refunds, tax exemptions |
| `invoices.py` | Check-out and invoice issuing |
| `reports.py` | Management statistics |
| `night_audit.py` | Close a day (also catches up missed days at start-up) |
| `audit.py` | Write and read the audit log, verify the hash chain |
| `backups.py` | Manual and daily backups, restore |
| `form_tokens.py` | One-time tokens that stop a form being submitted twice |
| `onboarding.py` | Walk-through state and checklist |

### 2.3 `src/hotel/persistence/` – the database (SQLite)

| File | Purpose |
|---|---|
| `db.py` | Opens SQLite with safe settings (foreign keys on, WAL journal, busy timeout) |
| `migrate.py` | Applies the numbered SQL migrations in order, once each |
| `unit_of_work.py` | `UnitOfWork`: one transaction (`BEGIN IMMEDIATE`) per business operation; commit or roll back as a whole |
| `convert.py` | Converts dates, money and enums to and from their database form |
| `backup.py` | Consistent copy of the live database (SQLite backup API) and integrity check |
| `migrations/0001…0020_*.sql` | The schema, built step by step: 0001 staff accounts, 0002 audit log, 0003 rooms, 0004 guests, 0005 settings, 0006 reservations, 0007 front desk, 0008 extras and taxes, 0009 discounts and payments, 0010 invoices, 0011 room inspection, 0012 night audit, 0013 seasonal rates, 0014 anonymisation, 0015 two-factor, 0016 API tokens, 0017 room moves, 0018 onboarding, 0019 tax payers and exemptions, 0020 archiving |
| `repositories/*.py` | One repository per area (`rooms.py`, `guests.py`, `reservations.py`, `billing.py`, `invoices.py`, `users.py`, `sessions.py`, `audit.py`, `taxes.py`, `extras.py`, `rates.py`, `reports.py`, `settings.py`, `night_audit.py`, `api_tokens.py`, `login_failures.py`, `form_tokens.py`, `onboarding.py`): SQL with `?` parameters only (no SQL injection), rows ↔ domain objects. `base.py` holds the shared helpers |

### 2.4 `src/hotel/web/` – the web interface (Flask)

| File | Purpose |
|---|---|
| `__init__.py` | `create_app()`: builds the Flask app, registers blueprints, filters and security hooks |
| `security.py` | Every request: sign-in check, role policy (**deny by default**), CSRF, security headers (CSP, no JavaScript), two-factor gate |
| `context.py` | Access to the services and current user inside a request; cookie names |
| `forms.py` | Reads form fields into typed values (dates, money, integers) with error messages |
| `messages.py` | Error code → translated message shown to the user |
| `errors.py` | Friendly error pages (404, 403, 500...) |
| `formatting.py` | Dates, amounts, phone numbers formatted for the chosen language |
| `preferences.py` | Language and theme kept in cookies |
| `countries.py` | Country names (EN/FR/AR) for the nationality suggestions |
| `charts.py` | Bar charts drawn as SVG on the server |
| `csv_export.py` | CSV downloads of report tables (safe against spreadsheet formula injection) |
| `rate_limit.py` | Limits requests per token on the JSON API |
| `removal.py` | Shared "Remove" confirmation (delete or archive) |
| `help.py` | Content of the Help page |
| `tour.py` | Content of the walk-through |

**`web/blueprints/`** – one file per area of the site, each with its URLs:
`auth` (sign in/out), `account` (password, two-factor, API tokens),
`dashboard`, `availability` (grid), `reservations`, `billing`, `invoices`,
`guests`, `rooms`, `extras`, `hotel_settings`, `staff`, `reports`,
`night_audit`, `audit`, `backups`, `preferences`, `help`, `welcome`
(walk-through), `health` (`/health` for Docker), `api` (read-only JSON API).

**`web/templates/`** – HTML pages (Jinja2), one folder per blueprint:
`base.html` and `layouts/app.html` (page frame, menu), `macros/` (reusable
pieces: form fields, icons, paging, charts, bill, archive buttons...),
`partials/` (flash messages, sign-in decoration, language/theme switch,
account menu, checklist), then `auth/`, `account/`, `dashboard/`,
`availability/`, `reservations/`, `billing/`, `invoices/`, `guests/`,
`rooms/`, `extras/`, `settings/`, `staff/`, `reports/`, `night_audit/`,
`audit/`, `backups/`, `help/`, `welcome/`, `removal/`, `errors/`.

**`web/static/`** – `css/app.css` (all styles, light and dark themes, right-to-left
for Arabic), `fonts/` (Inter, Playfair Display, Great Vibes, Noto Sans Arabic,
with their OFL licences, served locally), `img/favicon.svg`.

### 2.5 Other packages

| Path | Purpose |
|---|---|
| `src/hotel/translations/` | `messages.pot` (template of all texts), then `fr/` and `ar/`: `messages.po` (translations, editable) and `messages.mo` (compiled) |
| `src/hotel/data/common_passwords.txt` | Passwords refused because they are too common |

## 3. `tests/` – automated tests (pytest)

| Folder | What is tested | Examples |
|---|---|---|
| `conftest.py` | Shared fixtures: a fresh database, a fixed clock, a demo hotel, signed-in users | |
| `unit/` | Domain only, very fast, no database | `test_money.py`, `test_period.py`, `test_billing.py`, `test_reservation_rules.py`, `test_totp.py` (RFC test vectors), `test_architecture.py` (layer rules) |
| `integration/` | Services against a real SQLite file | `test_booking.py`, `test_change_and_cancel.py`, `test_check_out_and_invoices.py`, `test_removal.py`, `test_backups.py` |
| `e2e/` | Whole HTTP requests through Flask | `test_auth_flow.py`, `test_route_policy.py` (every page declares who may use it), `test_booking_pages.py`, `test_translations.py` |

About 720 tests, 90 % minimum coverage, run on Linux and Windows with
Python 3.11 and 3.13 by CI.

## 4. `docs/` – documentation

| File | Content |
|---|---|
| `requirements.md` | **Analysis**: actors, entities, business rules BR1–BR26, decisions on unclear points, non-functional requirements, main scenarios |
| `data-model.md` | **ER diagram** and full relational schema (keys, constraints) |
| `architecture.md` | Layers, package layout, design decisions, request life cycle, error handling |
| `adr/0001…0006` | Architecture Decision Records: why Flask, why SQLite with raw SQL, server-side sessions, the room-night table, error codes, two-factor |
| `diagrams/*.drawio` | UML: two use case diagrams, two class diagrams, architecture (open at app.diagrams.net) |
| `roadmap.md` | Sprints, user stories, Definition of Done, Git workflow, risks |
| `checkpoints.md` | The professor's checkpoints CP1–CP4 and where each is answered; task allocation |
| `security.md` | Threat review, authorization matrix, validation rules |
| `asvs.md` | OWASP ASVS 5.0 Level 1 self-assessment |
| `test-evidence.md` | Requirement → test that proves it |
| `manual-checks.md` | Browser and Windows checks done by hand |
| `user-guide.md` | Every page and button per role, with examples |
| `api.md` | JSON API reference |
| `deployment.md` | Installing, backups, Docker, HTTPS |
| `translations.md` | How texts are translated and reviewed |
| `project-structure.md` | This file |
| `screenshots/` | Pictures used by the README |

## 5. Tools and delivery

| Path | Purpose |
|---|---|
| `scripts/i18n_sync.py` | After changing interface text: extract, merge and compile the French/Arabic catalogues |
| `scripts/i18n_review.py` | Export/import translations to a spreadsheet for a human review |
| `packaging/windows/launcher.py` | Entry point of the Windows `.exe`: starts the server, opens the browser |
| `packaging/windows/hotel.spec` | PyInstaller recipe for the `.exe` |
| `packaging/windows/README.txt` | Instructions shipped with the `.exe` |
| `deploy/compose.yaml` | Docker Compose: the app + Caddy |
| `deploy/Caddyfile` | Caddy configuration: automatic HTTPS in front of the app |
| `.github/workflows/ci.yml` | CI on every push: lint, security scan, tests (Ubuntu + Windows, Python 3.11 + 3.13), Docker image, Windows exe |
| `.github/dependabot.yml` | Weekly dependency update proposals |
| `.github/pull_request_template.md`, `ISSUE_TEMPLATE/user_story.md` | Templates for pull requests and user-story issues |
