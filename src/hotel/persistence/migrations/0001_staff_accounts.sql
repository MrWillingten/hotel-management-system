-- Sprint 1: staff accounts, server-side sessions and login throttling.
-- Conventions used in every table:
--   * timestamps are UTC ISO-8601 text with microseconds (they sort correctly as text)
--   * booleans are INTEGER 0/1 guarded by a CHECK constraint
--   * `version` supports optimistic locking

CREATE TABLE app_user (
    id                   INTEGER PRIMARY KEY,
    username             TEXT    NOT NULL UNIQUE
                                 CHECK (length(username) BETWEEN 3 AND 32),
    full_name            TEXT    NOT NULL CHECK (length(full_name) BETWEEN 1 AND 100),
    password_hash        TEXT    NOT NULL,
    role                 TEXT    NOT NULL CHECK (role IN ('RECEPTIONIST', 'MANAGER')),
    is_active            INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1)),
    failed_attempts      INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until         TEXT,
    created_at           TEXT    NOT NULL,
    version              INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)
);

-- The cookie holds a random token; only its SHA-256 hash is stored here.
CREATE TABLE user_session (
    token_hash   TEXT    PRIMARY KEY CHECK (length(token_hash) = 64),
    user_id      INTEGER NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    created_at   TEXT    NOT NULL,
    last_seen_at TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    ip           TEXT,
    user_agent   TEXT
);
CREATE INDEX ix_user_session_user ON user_session (user_id);

-- Failed sign-ins per client address, used to slow down password guessing
-- across many accounts (per-account lockout is stored on app_user).
CREATE TABLE login_failure (
    id       INTEGER PRIMARY KEY,
    ip       TEXT NOT NULL,
    username TEXT,
    at       TEXT NOT NULL
);
CREATE INDEX ix_login_failure_ip_at ON login_failure (ip, at);
