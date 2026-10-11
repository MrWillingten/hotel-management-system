-- Sprint 6 (story 6.1): second factor (TOTP) for sign-in.
-- The shared secret must be readable to compute codes, so it cannot be hashed
-- like a password; it is useless without the password (scrypt) of the account.
ALTER TABLE app_user ADD COLUMN totp_secret TEXT;
ALTER TABLE app_user ADD COLUMN totp_pending_secret TEXT;
-- The time step of the last accepted code: a code is never accepted twice.
ALTER TABLE app_user ADD COLUMN totp_last_step INTEGER;
ALTER TABLE app_user ADD COLUMN totp_enabled_at TEXT;
-- Managers without a second factor may work until this instant, then must enrol.
ALTER TABLE app_user ADD COLUMN totp_grace_until TEXT;

-- One-time recovery codes for a lost phone, stored as SHA-256 hashes.
CREATE TABLE recovery_code (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    code_hash TEXT    NOT NULL CHECK (length(code_hash) = 64),
    used_at   TEXT,
    UNIQUE (user_id, code_hash)
);

-- Between the password and the code: proves the password was right, for a few
-- minutes, without opening a session. The browser keeps the token, the
-- database only its hash.
CREATE TABLE login_challenge (
    token_hash TEXT    PRIMARY KEY CHECK (length(token_hash) = 64),
    user_id    INTEGER NOT NULL REFERENCES app_user (id) ON DELETE CASCADE,
    expires_at TEXT    NOT NULL,
    attempts   INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0)
);
