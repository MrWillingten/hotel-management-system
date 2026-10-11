-- Sprint 2: room categories, rooms, maintenance periods and blocked nights.

CREATE TABLE room_category (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 50),
    description TEXT    NOT NULL DEFAULT '' CHECK (length(description) <= 300),
    version     INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

-- `id` is a surrogate key so a room can be renumbered without breaking history.
CREATE TABLE room (
    id                INTEGER PRIMARY KEY,
    number            TEXT    NOT NULL UNIQUE CHECK (length(number) BETWEEN 1 AND 10),
    category_id       INTEGER NOT NULL REFERENCES room_category (id),
    capacity          INTEGER NOT NULL CHECK (capacity BETWEEN 1 AND 10),
    nightly_rate_mill INTEGER NOT NULL CHECK (nightly_rate_mill > 0),
    in_service        INTEGER NOT NULL DEFAULT 1 CHECK (in_service IN (0, 1)),
    notes             TEXT    NOT NULL DEFAULT '' CHECK (length(notes) <= 500),
    version           INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);
CREATE INDEX ix_room_category ON room (category_id);

-- end_date is the reopening day: the period is [start_date, end_date).
CREATE TABLE maintenance (
    id         INTEGER PRIMARY KEY,
    room_id    INTEGER NOT NULL REFERENCES room (id),
    start_date TEXT    NOT NULL,
    end_date   TEXT    NOT NULL,
    reason     TEXT    NOT NULL CHECK (length(reason) BETWEEN 1 AND 200),
    created_by INTEGER REFERENCES app_user (id),
    created_at TEXT    NOT NULL,
    CHECK (end_date > start_date)
);
CREATE INDEX ix_maintenance_room ON maintenance (room_id, start_date);

-- One row per room per blocked night. The primary key (room_id, night) is what
-- makes overlapping blocks impossible at the database level (ADR 0004).
-- Sprint 3 adds reservation nights to this table.
CREATE TABLE room_night (
    room_id        INTEGER NOT NULL REFERENCES room (id),
    night          TEXT    NOT NULL,
    maintenance_id INTEGER NOT NULL REFERENCES maintenance (id) ON DELETE CASCADE,
    PRIMARY KEY (room_id, night)
);
CREATE INDEX ix_room_night_maintenance ON room_night (maintenance_id);
