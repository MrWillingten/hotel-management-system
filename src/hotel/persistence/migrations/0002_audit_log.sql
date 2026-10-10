-- Sprint 2: append-only, hash-chained audit log.

CREATE TABLE audit_log (
    id        INTEGER PRIMARY KEY,
    at        TEXT    NOT NULL,
    user_id   INTEGER REFERENCES app_user (id),
    username  TEXT,
    action    TEXT    NOT NULL CHECK (length(action) BETWEEN 3 AND 64),
    entity    TEXT,
    entity_id TEXT,
    details   TEXT    NOT NULL DEFAULT '{}' CHECK (json_valid(details)),
    ip        TEXT,
    prev_hash TEXT    NOT NULL CHECK (length(prev_hash) = 64),
    hash      TEXT    NOT NULL UNIQUE CHECK (length(hash) = 64)
);
CREATE INDEX ix_audit_log_at ON audit_log (at);
CREATE INDEX ix_audit_log_user ON audit_log (user_id);

-- The application can only ever add entries. (Someone editing the file directly
-- could drop these triggers; the hash chain is what detects that.)
CREATE TRIGGER audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'the audit log is append-only');
END;

CREATE TRIGGER audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN
    SELECT RAISE(ABORT, 'the audit log is append-only');
END;
