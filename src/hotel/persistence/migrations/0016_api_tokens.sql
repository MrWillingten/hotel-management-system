-- Sprint 6 (story 6.3): personal tokens for the read-only JSON API.
-- The full token is shown once when it is created; only its SHA-256 hash is
-- kept, like session tokens. `prefix` (the first characters) lets people
-- recognise a token in the list without it being usable.
CREATE TABLE api_token (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    name         TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    token_hash   TEXT    NOT NULL UNIQUE CHECK (length(token_hash) = 64),
    prefix       TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    last_used_at TEXT,
    revoked_at   TEXT
);
CREATE INDEX ix_api_token_user ON api_token (user_id);
