-- Sprint 4: discounts granted by managers, and the money received or refunded.

-- A percentage (rate_bp) or a fixed amount (amount_mill), never both. Removing
-- a discount before check-out keeps the row (removed_at) for the history.
CREATE TABLE discount (
    id             INTEGER PRIMARY KEY,
    reservation_id INTEGER NOT NULL REFERENCES reservation (id),
    kind           TEXT    NOT NULL CHECK (kind IN ('PERCENT', 'FIXED')),
    rate_bp        INTEGER,
    amount_mill    INTEGER,
    reason         TEXT    NOT NULL CHECK (length(reason) BETWEEN 1 AND 200),
    approved_by    INTEGER REFERENCES app_user (id),
    created_at     TEXT    NOT NULL,
    removed_at     TEXT,
    removed_by     INTEGER REFERENCES app_user (id),
    CHECK (
        (kind = 'PERCENT' AND rate_bp BETWEEN 1 AND 10000 AND amount_mill IS NULL)
        OR (kind = 'FIXED' AND amount_mill > 0 AND rate_bp IS NULL)
    )
);
CREATE INDEX ix_discount_reservation ON discount (reservation_id);

-- Amounts are always positive (BR21); the kind says which way the money goes.
CREATE TABLE payment (
    id             INTEGER PRIMARY KEY,
    reservation_id INTEGER NOT NULL REFERENCES reservation (id),
    kind           TEXT    NOT NULL CHECK (kind IN ('DEPOSIT', 'PAYMENT', 'REFUND')),
    method         TEXT    NOT NULL CHECK (method IN ('CASH', 'CARD', 'TRANSFER')),
    amount_mill    INTEGER NOT NULL CHECK (amount_mill > 0),
    reference      TEXT    NOT NULL DEFAULT '' CHECK (length(reference) <= 60),
    paid_at        TEXT    NOT NULL,
    recorded_by    INTEGER REFERENCES app_user (id)
);
CREATE INDEX ix_payment_reservation ON payment (reservation_id);

-- Money movements are append-only, like the audit log: a mistake is corrected
-- with a new entry (a refund), so the cash book can always be reconciled.
CREATE TRIGGER payment_no_update BEFORE UPDATE ON payment
BEGIN
    SELECT RAISE(ABORT, 'payments are append-only');
END;
CREATE TRIGGER payment_no_delete BEFORE DELETE ON payment
BEGIN
    SELECT RAISE(ABORT, 'payments are append-only');
END;
