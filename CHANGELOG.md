# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

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
