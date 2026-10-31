# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased] – Sprint 7 (front-desk UX)

### Added
- Dashboard **In house** list (room, guest, departure, balance); the
  "Guests in the house" and "Due from guests in the house" cards lead to it.
- Departure and in-house rows show **Balance due: …** or **Paid**.
- Availability grid: filter by room category.
- `docs/research/hotel-ux-research.md`: how hotel PMS products are designed,
  with the recommendations that shape Sprint 7.
- Arrival rows show each room's housekeeping state, VIP, returning-guest
  stays, the deposit paid (or "Nothing paid yet") and the start of the
  note; rooms that are ready come first.
- New reservation, step 3: the stay total (before tax) for each room.
- Search box in the top bar: reservation code, invoice number, room number
  (an occupied room opens the guest's stay) or guest.
- Dashboard **Needs attention** panel: late arrivals, rooms not ready for
  today's arrivals, overdue departures, unpaid invoices; for managers also
  a day not closed, no backup in 24 hours, an altered audit log.
- Reports: presets (Yesterday, This month, Last month, Next 30 days, Year
  to date).
- Night audit: a preview of what closing the day will do, before the button.
- CP2 procedural prototype (`prototype/`).

### Changed
- Check in / Check out buttons on the dashboard show the room number, and
  the success messages name the guest and the room.
- Reservation page: one primary button per status; Cancel and No-show moved
  to an "Other actions" block at the bottom.
- Reserved nights on the grid are dotted, so they differ from occupied
  nights without relying on colour (WCAG 1.4.1).

### Fixed
- "Due from guests in the house" linked to "Unpaid after departure", a
  different list.

## Sprint 6 (unreleased, part of v1.0.0)

### Added
- Two-factor sign-in (TOTP, RFC 6238) under Account → Two-factor sign-in:
  scan a QR code with any authenticator app, confirm one code, receive 10
  one-time recovery codes. Required for managers (a reminder for 7 days,
  then every page asks to set it up); optional for receptionists, who may
  turn it off again. A code is never accepted twice; wrong codes count
  toward the account lockout. `hotel reset-totp USERNAME` for a lost phone.
  New dependency: `segno` (QR codes, pure Python). Migration 0015.
- Docker image (`Dockerfile`): unprivileged user, data in the `/data`
  volume, `HEALTHCHECK` on the new public `/health` page, dependencies from
  the hash-checked lock file. `deploy/compose.yaml` runs it behind Caddy
  (HTTPS with a local certificate authority) with a read-only file system
  and no capabilities. CI builds the image and checks it starts healthy.
- Read-only JSON API at `/api/v1/` (rooms, availability, reservations,
  report summary) with personal tokens that managers create and revoke under
  Account → API tokens: shown once, stored hashed, expiring, rate-limited.
  Documented in `docs/api.md`. Migration 0016.
- Windows program `hotel.exe` (PyInstaller, one file, no Python needed):
  first start asks for the manager account, then opens the browser; data in
  `%LOCALAPPDATA%\HotelMedina`. Built and smoke-tested by CI on Windows and
  kept as an artifact. `hotel run --open-browser`. The sign-in page shows
  the right command (`hotel.exe` or `python -m hotel`).
- Move guests to another room ("Move" next to a room on the reservation):
  the nights from tonight on move, nights already spent stay on the bill
  under the old room ("Left on …"); the new room is checked like a booking
  (free, big enough, in service; closest rooms proposed first). The guest
  keeps the locked price by default; a manager may charge the new room's
  price. The old room is marked to clean. Audited. Migration 0017.

- User guide (`docs/user-guide.md`): every page and button per role, what it
  is for and an example; a translated **Help** page in the menu shows each
  role only the topics it can use (story 6.10).
- Thin scrollbars in the theme's colours, light and dark (story 6.11).
- Sign-in page (story 6.12): the hotel's name writes itself as an animated
  signature in Great Vibes (bundled, OFL) with a gold flourish; the form
  side has slowly drifting diagonal stripes and a light sweep, the form sits
  on a raised card. CSS and SVG only; still for people who ask for reduced
  motion.
- Invoice redesigned as a sheet of paper (story 6.13), always in the light
  "paper" palette (also in the dark theme): letterhead with the signature
  name and a gold rule, INVOICE title and number, billed-to / stay /
  reservation blocks, the bill, a "Paid in full" or "Balance due" stamp,
  the payments table, and a thank-you line. Ctrl+P prints only the sheet on
  A4 with page numbers ("Save as PDF" for a PDF).
- Walk-through for new accounts (story 6.14): the dashboard invites new
  staff to a short tour (6 steps for receptionists, 8 for managers; Back,
  Next, Skip; reopen from Help) and shows a "Getting started" checklist
  that ticks itself from the audit log as each task is done for the first
  time (register a guest, book, check in, take a payment, check out; for
  managers also add a room, add staff, two-factor, backup). Migration 0018.

### Changed (corrections requested 18 Oct)
- Real checks on guest details (story 6.15): passport numbers need 6–9
  letters and digits including a digit; phone numbers are checked against
  each country's real numbering plan with Google's libphonenumber
  (`phonenumberslite`, new dependency) and stored as E.164, shown spaced
  (`+216 20 123 456`); e-mail addresses are checked part by part; the
  nationality is typed with country suggestions in the interface language
  (no JavaScript: an HTML `datalist`) and stored as its ISO code. Clearer
  error messages; demo data uses valid numbers for each country.
- Taxes by guest and per stay (story 6.16): each tax rule says who pays
  (everyone, foreign guests only, or nationals of the hotel's country only,
  a new setting, Tunisia by default), decided by the guest's nationality
  (or a CIN). Managers can exempt one stay from one tax with a reason on its
  bill until the invoice is issued; exemptions are listed on the invoice and
  audited. The demo tourist tax now concerns foreign guests only.
  Migration 0019.
- Delete or archive (story 6.17): managers can remove guests, rooms, extra
  services, tax rules and staff accounts ("Remove…"). A record never used is
  deleted; one with history is archived: hidden from lists, forms and
  suggestions, history intact, restorable (archived lists under
  "Archived: n"). Removal is refused while it would break something current
  (a room with future bookings, a guest with a stay to come, oneself, the
  last manager). The confirmation page says which and why; every removal is
  audited. Migration 0020.

### Security (story 6.6)
- OWASP ASVS 5.0 Level 1 self-assessment (`docs/asvs.md`): 58 requirements
  met, 12 not applicable. Gaps fixed: every cookie is `__Host-` prefixed
  behind HTTPS; sign-out sends `Clear-Site-Data`; the common-password list
  grew from 1,193 to 7,309 entries of 12+ characters.
- `docs/security.md`: authorization matrix, input validation rules,
  brute-force and lockout-abuse notes, dependency update time frames.
- `docs/test-evidence.md` maps every scenario, business rule and decision
  to its tests (a test checks the references stay valid);
  `docs/manual-checks.md` lists the browser and real-Windows checks.

## [0.9.0] – Sprint 5: Reports, operations, languages (code complete)

### Added
- Reports page (managers) for any range of up to two years: occupancy
  per day or month (rooms under maintenance excluded), nights sold, room
  value, average daily rate, revenue per available room, revenue counted
  when invoiced (accommodation, services, fees, taxes), cash received
  per method, reservations made, cancellations and no-shows, nights per
  category, availability by category, outstanding balances.
- Server-side SVG charts (no JavaScript): occupancy over time, revenue by
  type, nights per category; themed, mirrored in right-to-left languages.
- CSV export of the report tables, protected against formula injection,
  without identity documents or contact details, audited.
- Night audit: closes each finished day (no-shows, overdue departures
  flagged, frozen daily snapshot); `hotel night-audit`, a manager page
  and an automatic catch-up at start-up; safe to run twice.
- Seasonal rate periods per category and a weekend surcharge on chosen
  nights (default Saturday and Sunday); period > weekend > base rate;
  booked nights keep their prices.
- Guest anonymisation after a configurable time without a stay (default
  24 months), confirmed by a manager; invoices keep their copy.
- Translation review workflow (`scripts/i18n_review.py`), amounts
  isolated with `<bdi>`, test for Western digits in Arabic.
- Demo data v2: about four months of replayed history with seasonal
  prices and a night audit every day.
- A link from the room form to the categories page.

## [0.4.0] – Sprint 4: Front desk and billing

### Added
- Front-desk dashboard: arrivals (late ones flagged), departures, guests
  in the house, occupancy tonight (rooms under maintenance excluded),
  money due from guests in the house, unpaid invoices, rooms to clean.
- Check-in (BR17) from the arrival day, never while the previous guest
  of a room is still checked in; warning for rooms not yet cleaned.
- No-show after the arrival time, charged like a late cancellation;
  the nights are released.
- Housekeeping per room: dirty → cleaned → inspected (ready); check-out
  marks rooms dirty; the dashboard lists rooms not ready and rooms under
  maintenance.
- `hotel reset-password USERNAME`: a way back in when the only manager
  forgets their password (temporary password, sessions ended, audited).
- Extra-services catalogue (manager) and charges to a stay (BR19):
  only while checked in, dated within the stay, price copied (BR20);
  managers void a wrong charge with a reason.
- Hotel settings: check-in/out times, cancellation fee, window and
  grace period, discount cap. The cancellation and no-show rules use them.
- Tax rules (Strategy pattern): percentage of the accommodation or of
  the services, or an amount per adult per night. Prices stay
  tax-exclusive; each tax is its own line, rounded half-up.
- Bill preview built by one pure function; golden tests for the brief's
  scenario §4.7 with and without taxes.
- Discounts (Strategy pattern): manager only, reason required,
  accommodation only, capped (30 % by default).
- Deposits, payments and manager-only refunds; never more than the
  balance due or the overpayment; append-only payment table.
- Check-out issues the invoice in the same transaction, numbered
  `F-YYYY-NNNNN` without gaps; early departures charge only the nights
  stayed and release the others. Cancellation and no-show fees are
  invoiced too. Invoices are immutable (database triggers) and have a
  print stylesheet.
- Demo data replays the last week: stays, extras, payments, check-outs,
  invoices, a no-show and one unpaid departure.

### Changed
- Cancellation texts show the configured rate instead of a fixed 20 %.
- A guest still in a room on their departure day keeps it "occupied".
- The dashboard roadmap placeholder is gone.

## [0.3.0] – Sprint 3: Reservations and availability

### Added
- Reservations for one or more rooms with adults and children per room
  (capacity rule BR7), prices locked per night, gap-free codes
  `R-YYYY-NNNNN`, do-not-rent guests refused.
- Booking flow: dates, guest (search or register and come back), rooms,
  review with the exact price, confirmation.
- Conflicts (scenario 4.3) name the room and nights and suggest up to five
  similar free rooms.
- Changes (scenario 4.4): dates, rooms and occupants with availability
  re-checked; kept nights keep their price, added nights use today's
  rate; old and new price shown before saving.
- Cancellation with the BR11 fee (20 % if less than 48 h before arrival at
  14:00, hotel time); rooms released immediately.
- Availability grid: rooms x 14 nights, colour plus text, links to book or
  open a reservation; keyboard accessible and right-to-left aware.
- Rooms show reserved/occupied tonight; guest pages list their bookings;
  room changes and maintenance that would strand a booking are refused.
- Concurrency protection: `BEGIN IMMEDIATE`, re-check, `room_night`
  primary key, a two-thread race test, and one-time form tokens against
  double submits.
- Demo data now includes about thirty reservations.

### Fixed
- Availability ignored maintenance nights when no reservation was being
  excluded (found by a test; the database key had still prevented any
  double booking).
- Screen-reader labels in the grid widened the page in right-to-left mode.

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
