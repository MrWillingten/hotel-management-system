# Checkpoints (Student Guide 2026-2027)

The professor's guide sets five mandatory milestones. This page shows where
each one is answered in the repository.

| Checkpoint | Date | Expected | Status |
|---|---|---|---|
| CP1 – Analysis | 19/10/2026 | Requirements, business rules, ER diagram, task allocation | ✅ see below |
| CP2 – Procedural prototype | 02/11/2026 | Working prototype with Python functions and collections | ✅ (see below) |
| CP3 – OOP development | 16/11/2026 | Object-oriented design and implementation of core features | ✅ |
| CP4 – Integration | 30/11/2026 | Integrated application, data persistence, testing | ✅ |
| Final demonstration | 14/12/2026 | Present and demonstrate the completed application | Demo script in preparation |

Final deliverables: working Python OOP application ✅, source code in a Git
repository ✅ ([GitHub](https://github.com/MrWillingten/hotel-management-system)),
project documentation ✅ (`docs/`), printed report of 10–15 pages + PDF (to write),
live demonstration.

---

## CP1 – Analysis

| Item | Where |
|---|---|
| **Requirements** | [requirements.md](requirements.md): summary, actors (§2), entities (§3), non-functional requirements (§6), main scenarios (§7) |
| **Business rules** | [requirements.md §4](requirements.md#4-business-rules): BR1–BR12 from the brief, BR13–BR26 derived; decisions on ambiguous points (§5) |
| **ER diagram** | [data-model.md](data-model.md#conceptual-erd): conceptual ERD (shown as a picture on GitHub) and the full relational schema with keys and constraints |
| **Task allocation** | Below |
| UML (extra) | [diagrams/](diagrams/README.md): use case and class diagrams |

### Task allocation

The project is done **individually** (one student), so every role belongs to
the same person; the work is divided **in time** instead of between people.

| Role | Responsibility | Done by |
|---|---|---|
| Analyst | Requirements, business rules, ER diagram | Student |
| Designer / architect | Layers, classes, database schema, decisions (ADRs) | Student |
| Developer | Python code, web pages, database | Student |
| Tester | Unit, integration and end-to-end tests | Student |
| Security reviewer | Threat review, ASVS self-assessment | Student |
| Writer / presenter | Documentation, report, demonstration | Student |

The work was planned as six two-week sprints, each a set of user stories
(GitHub issues) with acceptance criteria: see [roadmap.md](roadmap.md).

| Sprint | Content |
|---|---|
| 1 | Foundations: repository, CI, sign-in, themes, languages |
| 2 | Rooms, guests, staff accounts, audit log, backups |
| 3 | Reservations and availability |
| 4 | Front desk (check-in/out) and billing |
| 5 | Reports, night audit, translations |
| 6 | Extensions, hardening, report, demonstration |

AI assistance (Claude Code) was used and is declared in the README; every
commit written with it says so.

## CP2 – Procedural prototype

The core rules are plain **functions over collections**, which can be shown
on their own:

| Function | File | Collections used |
|---|---|---|
| `build_bill(...)` | `domain/billing.py` | lists of nights, charges, payments → bill lines |
| `taxes_for_stay(rules, national, exempt_rule_ids)` | `domain/taxes.py` | list of rules, `set` of exempted ids |
| `is_national(nationality, id_doc_type, home_country)` | `domain/taxes.py` | — |
| `plan_removal(uses, ...)` | `domain/removal.py` | number of uses → delete or archive |
| `normalize_phone`, `normalize_email`, `normalize_doc_number`, `normalize_country` | `domain/guests.py` | `frozenset` of country codes |
| `search_key(text)` | `domain/guests.py` | accent-free text for searching |
| `Pricing.rate_for(room, night)` | `domain/pricing.py` | list of seasonal rate periods |

## CP3 – OOP

Classes with encapsulation (`Money`, `StayPeriod`), inheritance (`HotelError`
hierarchy, `PercentDiscount`/`FixedDiscount`), polymorphism and the Strategy
pattern (`PercentTax`/`PerAdultNightTax`), composition (`Reservation` owns its
`BookedRoom`s and `RoomNight`s), state transitions (reservation life cycle).
See the class diagrams in [diagrams/](diagrams/README.md) and
[project-structure.md](project-structure.md).

## CP4 – Integration

Web application + command line using the same services; SQLite persistence
with migrations, transactions and backups; about 720 automated tests, 90 %
coverage, run by CI on Linux and Windows ([test-evidence.md](test-evidence.md)).
