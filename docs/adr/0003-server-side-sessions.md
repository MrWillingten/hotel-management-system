# ADR 0003 – Server-side sessions

**Status:** accepted (Sprint 1)

## Context
Flask's default session is a signed cookie: the server cannot revoke it. Logging
out, deactivating a user or changing a role would not end an existing session.

## Decision
The cookie `hotel_session` holds a random 256-bit token (`HttpOnly`,
`SameSite=Lax`, `Secure` behind HTTPS). The `user_session` table stores only the
token's SHA-256 hash, with creation, last-seen and expiry times. Sessions end
after 30 minutes of inactivity or 12 hours in total. Flask's own signed cookie is
kept only for flash messages and the CSRF token.

## Consequences
One small database read per request (and a write at most once a minute).
Logout, deactivation and role changes take effect immediately; a stolen copy of
the database does not contain usable session tokens.
