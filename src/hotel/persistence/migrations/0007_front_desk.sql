-- Sprint 4: check-in, no-show and housekeeping.

ALTER TABLE reservation ADD COLUMN no_show_at TEXT;

-- Housekeeping is not part of the room's description, so changing it does not
-- bump room.version: a receptionist marking a room clean must never make a
-- manager's simultaneous price change fail.
ALTER TABLE room ADD COLUMN housekeeping TEXT NOT NULL DEFAULT 'CLEAN'
    CHECK (housekeeping IN ('CLEAN', 'DIRTY'));

-- Front-desk lists (arrivals, departures, guests in the house) filter by status.
CREATE INDEX ix_reservation_status ON reservation (status, arrival);
