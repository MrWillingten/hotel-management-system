-- Sprint 3: reservations.

CREATE TABLE reservation (
    id                    INTEGER PRIMARY KEY,
    code                  TEXT    NOT NULL UNIQUE,
    guest_id              INTEGER NOT NULL REFERENCES guest (id),
    arrival               TEXT    NOT NULL,
    departure             TEXT    NOT NULL,
    status                TEXT    NOT NULL CHECK (status IN
                              ('CONFIRMED', 'CHECKED_IN', 'CHECKED_OUT', 'CANCELLED', 'NO_SHOW')),
    cancellation_fee_mill INTEGER CHECK (cancellation_fee_mill IS NULL OR cancellation_fee_mill >= 0),
    notes                 TEXT    NOT NULL DEFAULT '' CHECK (length(notes) <= 500),
    created_by            INTEGER REFERENCES app_user (id),
    created_at            TEXT    NOT NULL,
    cancelled_at          TEXT,
    checked_in_at         TEXT,
    checked_out_at        TEXT,
    version               INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    CHECK (departure > arrival)  -- business rule BR4
);
CREATE INDEX ix_reservation_guest ON reservation (guest_id);
CREATE INDEX ix_reservation_dates ON reservation (arrival, departure, status);

CREATE TABLE reservation_room (
    reservation_id INTEGER NOT NULL REFERENCES reservation (id) ON DELETE CASCADE,
    room_id        INTEGER NOT NULL REFERENCES room (id),
    adults         INTEGER NOT NULL CHECK (adults BETWEEN 1 AND 10),
    children       INTEGER NOT NULL DEFAULT 0 CHECK (children BETWEEN 0 AND 10),
    PRIMARY KEY (reservation_id, room_id)
);
CREATE INDEX ix_reservation_room_room ON reservation_room (room_id);

-- room_night now holds reservation nights as well as maintenance nights.
-- SQLite cannot add a foreign key to an existing table, so the table is rebuilt
-- (the documented "create, copy, drop, rename" procedure).
CREATE TABLE room_night_new (
    room_id        INTEGER NOT NULL REFERENCES room (id),
    night          TEXT    NOT NULL,
    reservation_id INTEGER REFERENCES reservation (id),
    maintenance_id INTEGER REFERENCES maintenance (id) ON DELETE CASCADE,
    rate_mill      INTEGER CHECK (rate_mill IS NULL OR rate_mill > 0),
    PRIMARY KEY (room_id, night),
    -- every blocked night belongs to exactly one reservation or one maintenance
    CHECK ((reservation_id IS NULL) <> (maintenance_id IS NULL)),
    -- a reserved night always carries the price locked at booking time
    CHECK (reservation_id IS NULL OR rate_mill IS NOT NULL)
);
INSERT INTO room_night_new (room_id, night, maintenance_id)
    SELECT room_id, night, maintenance_id FROM room_night;
DROP TABLE room_night;
ALTER TABLE room_night_new RENAME TO room_night;
CREATE INDEX ix_room_night_maintenance ON room_night (maintenance_id);
CREATE INDEX ix_room_night_reservation ON room_night (reservation_id);

-- Gap-free yearly sequences (reservation codes now, invoice numbers later).
-- Incremented inside the business transaction, so a rollback leaves no gap.
CREATE TABLE counter (
    name  TEXT    NOT NULL,
    year  INTEGER NOT NULL,
    value INTEGER NOT NULL CHECK (value >= 0),
    PRIMARY KEY (name, year)
);

-- One-time tokens that stop a double click from submitting a form twice.
CREATE TABLE form_token (
    token_hash TEXT    PRIMARY KEY CHECK (length(token_hash) = 64),
    user_id    INTEGER NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL
);
