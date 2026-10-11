# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.2.0] – Sprint 2: Rooms, guests, staff, audit, backups

### Added
- Tamper-evident audit log: SHA-256 hash chain, append-only triggers,
  manager viewer with filters, `hotel audit verify`.
- Staff management: create with temporary password (forced change),
  edit, deactivate (ends sessions), reset password, unlock; last-manager
  protection; everyone can change their own password.
- Room categories and rooms (unique numbers, capacity, nightly rate),
  out-of-service flag, tonight's status.
- Maintenance periods stored as one `room_night` row per night with a
  primary key that makes overlapping blocks impossible.
- Guests: validated CIN/passport (unique), probable-duplicate warning,
  accent-insensitive search on name/document/phone/e-mail, pagination,
  whitelisted sorting, masked document numbers with audited reveal,
  VIP and do-not-rent flags, localised country list.
- Backups with SQLite's online backup API: daily rotation, manual
  backups, automatic backup before upgrades, `hotel restore` with a
  safety copy.
- `hotel seed --demo` with fictional data and a DEMO DATA banner.
- Hash-pinned dependency lock files used by CI.

### Fixed
- `.gitignore` patterns are anchored to the project root, so folders
  such as `templates/backups/` are no longer ignored.

## [0.1.0] – Sprint 1: Foundations

### Added
- Project structure (`src/` layout), packaging, CLI (`python -m hotel`).
- Domain: `Money` (integer millimes, half-up rounding), `StayPeriod` (half-open
  date ranges), `Clock`, user lockout policy, password policy, error codes.
- Persistence: SQLite connections with mandatory PRAGMAs, versioned migrations,
  Unit of Work, user / session / login-failure repositories, optimistic locking.
- Authentication: first manager created from the CLI, scrypt hashing, server-side
  sessions (idle and absolute timeouts), account lockout, per-address throttling,
  timing-equalised failures.
- Web: deny-by-default access policies, CSRF protection, security headers,
  friendly error pages with incident ids, Post/Redirect/Get.
- "Cognac" theme: light, dark and system modes, responsive layout, bundled fonts,
  reduced-motion support.
- English, French and Arabic (right-to-left) interface.
- 180+ tests; GitHub Actions on Ubuntu and Windows (Python 3.11 and 3.13),
  ruff, bandit, pip-audit; Dependabot.
- Documentation: requirements, architecture, data model, security review,
  roadmap, deployment, translations, five ADRs.
