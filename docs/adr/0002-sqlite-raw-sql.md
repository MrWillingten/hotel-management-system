# ADR 0002 – SQLite with hand-written SQL behind repositories

**Status:** accepted (Sprint 1)

## Context
Data must persist without a database server. The deliverables include an ERD and
a relational schema.

## Options
* **JSON files**: no transactions, no constraints, last writer wins.
* **SQLite + SQLAlchemy ORM**: less code, but generated SQL is harder to defend
  and the ORM was not studied in class.
* **SQLite + standard-library `sqlite3` + repositories**: every query is visible;
  the schema maps one-to-one to the ERD.

## Decision
SQLite through `sqlite3`, parameterised SQL only, one repository per aggregate,
transactions managed by a Unit of Work (`BEGIN IMMEDIATE`). Schema changes are
numbered SQL migrations tracked with `PRAGMA user_version`.

## Consequences
More mapping code (row ↔ object). Foreign keys must be enabled on every
connection (done in `connect()`, tested). `STRICT` tables are not used, because
some Linux distributions ship SQLite versions that are too old; CHECK
constraints and domain validation cover types instead. Minimum SQLite: 3.35.
