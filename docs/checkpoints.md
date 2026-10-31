# Checkpoints (Student Guide 2026-2027)

The professor's guide sets five mandatory milestones. This page shows where
each one is answered in the repository.

| Checkpoint | Date | Expected | Status |
|---|---|---|---|
| CP1 – Analysis | 19/10/2026 | Requirements, business rules, ER diagram, task allocation | ✅ see below |
| CP2 – Procedural prototype | 02/11/2026 | Working prototype with Python functions and collections | ✅ `prototype/` |
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

[prototype/](../prototype/README.md): the core rules of CP1 written with
functions, `dict`, `list`, `tuple` and `set` only (no classes, no database),
with a terminal menu and the brief's scenarios checked:

```
python prototype/hotel_prototype.py
python prototype/scenarios.py
```

Its README maps every CP1 business rule to the function that enforces it. The CP2
document (8 pages) is built from `report/cp2/` with `build.sh "Student Name"`.
The application itself also keeps several rules as plain functions
(`build_bill`, `taxes_for_stay`, `plan_removal`, the guest checks in
`domain/guests.py`).

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
