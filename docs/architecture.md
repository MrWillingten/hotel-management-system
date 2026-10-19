# Architecture

## Layers

```
 web/          Flask blueprints, Jinja templates, access policies, error pages
 cli.py        command line (run, init-db, create-manager, ...)
   │  both call ↓ (never the other way round)
 services/     use cases: sign in, reserve, check in, bill, report
   │
 domain/       pure Python: entities, value objects, rules, error codes
   ↑
 persistence/  SQLite: connections, migrations, Unit of Work, repositories
```

**Dependency rule:** `web → services → domain ← persistence`. The domain imports
nothing from the project and no third-party library; services never import Flask.
`tests/unit/test_architecture.py` enforces this on every build.

`bootstrap.build_services()` is the only place where the parts are wired together
(the *composition root*). The web application and the CLI both call it, which is
why the business logic can be tested and used without a web server.

## Package layout

| Path | Responsibility |
|---|---|
| `src/hotel/config.py` | Settings from environment variables; production is the default |
| `src/hotel/secret_key.py` | Generates and protects the cookie-signing key |
| `src/hotel/bootstrap.py` | Composition root |
| `src/hotel/cli.py` | Command-line interface |
| `src/hotel/domain/` | `Money`, `StayPeriod`, `Clock`, users, rooms, guests, reservations, extras, taxes, `build_bill()`, invoices, settings, error hierarchy |
| `src/hotel/services/` | One service per area (auth, users, rooms, guests, reservations, front desk, extras, hotel settings, billing, invoices, backups, audit), role checks |
| `src/hotel/persistence/` | `connect()`, migrations, `UnitOfWork`, repositories |
| `src/hotel/web/` | `create_app()`, security hooks, blueprints, templates, static files |
| `src/hotel/translations/` | French and Arabic catalogues |
| `tests/unit`, `tests/integration`, `tests/e2e` | Domain only · services with a real SQLite file · full HTTP requests |

## Key design decisions

| Decision | Why |
|---|---|
| Flask + Jinja, server-rendered | Small enough to explain end to end; does not impose its own architecture; no JavaScript build chain ([ADR 0001](adr/0001-flask-server-rendered.md)) |
| SQLite + `sqlite3` + hand-written SQL | No server, ACID transactions, every query is visible and parameterised ([ADR 0002](adr/0002-sqlite-raw-sql.md)) |
| Server-side sessions | Logout, deactivation and role changes take effect immediately ([ADR 0003](adr/0003-server-side-sessions.md)) |
| `room_night` table with `UNIQUE(room_id, night)` | The database itself makes double booking impossible ([ADR 0004](adr/0004-room-night-table.md)) |
| Error codes, translated in the web layer | Domain stays language-independent; EN/FR/AR messages ([ADR 0005](adr/0005-i18n-error-codes.md)) |
| Composition over inheritance for rooms | Room categories differ in data, not behaviour, so they are rows, not subclasses |
| Inheritance where behaviour differs | Exception hierarchy; tax rules (`PercentTax`, `PerAdultNightTax`) and discounts (`PercentDiscount`, `FixedDiscount`) as Strategy classes |
| The bill is one pure function | `build_bill()` is used by the preview, the desk balance, the check-out preview and the invoice, so they can never disagree |
| Money as integer millimes | Exact arithmetic; explicit half-up rounding |
| Injected `Clock` | Time-dependent rules (48 h fee, sessions, lockout) are testable |

## Request lifecycle (sign-in example)

1. `security.load_current_user` reads the session cookie and asks `AuthService` for the user.
2. `security.enforce_access_policy` checks the view's declared policy (deny by default).
3. Flask-WTF verifies the CSRF token on the POST.
4. The view calls `AuthService.login()`, which opens one `UnitOfWork` transaction:
   throttle check → user lookup → scrypt verification → lockout bookkeeping →
   new session row. The error, if any, is raised **after** the commit so failure
   counters are kept.
5. The view sets the `HttpOnly`, `SameSite=Lax` cookie and redirects (Post/Redirect/Get).
6. `security.add_security_headers` adds CSP, `nosniff`, `X-Frame-Options`,
   `Referrer-Policy`, `Cache-Control: no-store`, and HSTS behind HTTPS.

## Error handling

The domain raises `HotelError` subclasses carrying a *code* and *parameters*.
`web/errors.py` maps each class to an HTTP status and `web/messages.py` turns the
code into a sentence in the user's language. Unexpected exceptions are logged with
a traceback under a short incident id; the user only sees the id.

| Exception | HTTP |
|---|---|
| `ValidationError` | 400, form re-shown with field messages |
| `AuthenticationError` | 401 |
| `PermissionDeniedError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError`, `StaleDataError`, `BusinessRuleViolation`, `InvalidStateTransitionError` | 409 |
| anything else | 500, generic page + incident id |

## Diagrams

UML use case diagrams, the domain class diagrams and the layer diagram are in
[diagrams/](diagrams/README.md) as draw.io files; the class diagrams were read from the code.
