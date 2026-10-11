-- Sprint 2: key/value settings (demo-data flag; hotel settings arrive in Sprint 4).

CREATE TABLE setting (
    key   TEXT PRIMARY KEY CHECK (length(key) BETWEEN 1 AND 64),
    value TEXT NOT NULL CHECK (length(value) <= 1000)
);
