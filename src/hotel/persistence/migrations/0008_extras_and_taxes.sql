-- Sprint 4: extra services, the charges made for them, and tax rules.

-- The catalogue. Deactivated, never deleted (BR26).
CREATE TABLE extra (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL UNIQUE COLLATE NOCASE CHECK (length(name) BETWEEN 1 AND 60),
    unit_price_mill INTEGER NOT NULL CHECK (unit_price_mill > 0),
    is_active       INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    version         INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

-- Name and price are copied at charge time (BR20). A wrong charge is voided,
-- never deleted, so the history of the bill stays visible.
CREATE TABLE service_charge (
    id              INTEGER PRIMARY KEY,
    reservation_id  INTEGER NOT NULL REFERENCES reservation (id),
    extra_id        INTEGER NOT NULL REFERENCES extra (id),
    description     TEXT    NOT NULL CHECK (length(description) BETWEEN 1 AND 60),
    quantity        INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    unit_price_mill INTEGER NOT NULL CHECK (unit_price_mill > 0),
    charge_date     TEXT    NOT NULL,
    created_by      INTEGER REFERENCES app_user (id),
    created_at      TEXT    NOT NULL,
    voided_at       TEXT,
    voided_by       INTEGER REFERENCES app_user (id),
    void_reason     TEXT CHECK (void_reason IS NULL OR length(void_reason) BETWEEN 1 AND 200),
    CHECK ((voided_at IS NULL) = (void_reason IS NULL))
);
CREATE INDEX ix_service_charge_reservation ON service_charge (reservation_id);

-- A percentage (rate_bp) or an amount per adult per night (amount_mill), never both.
CREATE TABLE tax_rule (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    kind        TEXT    NOT NULL CHECK (kind IN ('PERCENT', 'PER_ADULT_NIGHT')),
    rate_bp     INTEGER,
    amount_mill INTEGER,
    applies_to  TEXT    NOT NULL CHECK (applies_to IN ('ACCOMMODATION', 'SERVICES')),
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    version     INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    CHECK (
        (kind = 'PERCENT' AND rate_bp BETWEEN 1 AND 10000 AND amount_mill IS NULL)
        OR (kind = 'PER_ADULT_NIGHT' AND amount_mill > 0 AND rate_bp IS NULL
            AND applies_to = 'ACCOMMODATION')
    )
);
