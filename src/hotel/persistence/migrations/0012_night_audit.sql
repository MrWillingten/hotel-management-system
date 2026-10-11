-- Sprint 5 (story 5.4): the night audit closes each day with a snapshot.
-- The primary key on the day is what makes running the audit twice harmless.
CREATE TABLE daily_snapshot (
    day                TEXT    PRIMARY KEY,
    nights_sold        INTEGER NOT NULL CHECK (nights_sold >= 0),
    nights_sellable    INTEGER NOT NULL CHECK (nights_sellable >= 0),
    room_value_mill    INTEGER NOT NULL,
    invoiced_mill      INTEGER NOT NULL,
    cash_mill          INTEGER NOT NULL,
    reservations_made  INTEGER NOT NULL CHECK (reservations_made >= 0),
    cancellations      INTEGER NOT NULL CHECK (cancellations >= 0),
    no_shows           INTEGER NOT NULL CHECK (no_shows >= 0),
    overdue_departures INTEGER NOT NULL CHECK (overdue_departures >= 0),
    created_at         TEXT    NOT NULL,
    created_by         INTEGER REFERENCES app_user (id)
);
