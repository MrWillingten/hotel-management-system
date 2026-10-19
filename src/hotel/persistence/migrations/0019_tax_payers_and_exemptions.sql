-- Sprint 6 (story 6.16): taxes by guest and per stay.
-- Who a rule taxes; existing rules keep taxing everyone.
ALTER TABLE tax_rule ADD COLUMN payers TEXT NOT NULL DEFAULT 'EVERYONE'
    CHECK (payers IN ('EVERYONE', 'FOREIGN', 'NATIONALS'));

-- A manager's decision that one stay does not pay one tax. Allowed only until
-- the invoice is issued (checked by the service); the invoice then holds the
-- taxes as they were, and this row records why one was missing.
CREATE TABLE tax_exemption (
    id             INTEGER PRIMARY KEY,
    reservation_id INTEGER NOT NULL REFERENCES reservation (id) ON DELETE CASCADE,
    tax_rule_id    INTEGER NOT NULL REFERENCES tax_rule (id),
    reason         TEXT    NOT NULL CHECK (length(reason) BETWEEN 1 AND 200),
    created_at     TEXT    NOT NULL,
    created_by     INTEGER REFERENCES app_user (id),
    UNIQUE (reservation_id, tax_rule_id)
);
