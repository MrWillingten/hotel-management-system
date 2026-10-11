-- Sprint 4: invoices issued at check-out (BR22).

-- Header: who, what stay, and the totals (stored for reports; recomputable
-- from the lines). Guest name and reservation code are copied, not joined.
CREATE TABLE invoice (
    id               INTEGER PRIMARY KEY,
    number           TEXT    NOT NULL UNIQUE,
    reservation_id   INTEGER NOT NULL UNIQUE REFERENCES reservation (id),
    reservation_code TEXT    NOT NULL,
    guest_name       TEXT    NOT NULL,
    arrival          TEXT    NOT NULL,
    departure        TEXT    NOT NULL,
    issued_at        TEXT    NOT NULL,
    issued_by        INTEGER REFERENCES app_user (id),
    subtotal_mill    INTEGER NOT NULL,
    discount_mill    INTEGER NOT NULL CHECK (discount_mill >= 0),
    tax_mill         INTEGER NOT NULL CHECK (tax_mill >= 0),
    total_mill       INTEGER NOT NULL CHECK (total_mill >= 0),
    paid_mill        INTEGER NOT NULL,
    balance_mill     INTEGER NOT NULL,
    CHECK (total_mill = subtotal_mill - discount_mill + tax_mill),
    CHECK (balance_mill = total_mill - paid_mill)
);

CREATE TABLE invoice_line (
    invoice_id  INTEGER NOT NULL REFERENCES invoice (id),
    line_no     INTEGER NOT NULL CHECK (line_no >= 1),
    kind        TEXT    NOT NULL CHECK (kind IN
                    ('NIGHTS', 'EXTRA', 'FEE', 'DISCOUNT', 'DISCOUNT_CAP', 'TAX')),
    label       TEXT    NOT NULL,
    quantity    INTEGER NOT NULL,
    unit_mill   INTEGER NOT NULL,
    amount_mill INTEGER NOT NULL,
    first_date  TEXT,
    last_date   TEXT,
    rate_bp     INTEGER,
    PRIMARY KEY (invoice_id, line_no)
);

-- An issued invoice can never change; corrections are new entries (BR22).
CREATE TRIGGER invoice_no_update BEFORE UPDATE ON invoice
BEGIN
    SELECT RAISE(ABORT, 'issued invoices are immutable');
END;
CREATE TRIGGER invoice_no_delete BEFORE DELETE ON invoice
BEGIN
    SELECT RAISE(ABORT, 'issued invoices are immutable');
END;
CREATE TRIGGER invoice_line_no_update BEFORE UPDATE ON invoice_line
BEGIN
    SELECT RAISE(ABORT, 'issued invoices are immutable');
END;
CREATE TRIGGER invoice_line_no_delete BEFORE DELETE ON invoice_line
BEGIN
    SELECT RAISE(ABORT, 'issued invoices are immutable');
END;
