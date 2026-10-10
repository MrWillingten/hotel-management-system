# ADR 0005 – Error codes and gettext translations

**Status:** accepted (Sprint 1)

## Context
The interface must be available in English, French and Arabic (right-to-left).
Business rules must not depend on a language.

## Decision
Domain and services raise `HotelError` subclasses with a stable code
(`password.too_short`) and parameters (`min_length=12`). The web layer maps
codes to gettext messages (`web/messages.py`); the CLI uses English. Language
is chosen by cookie, else the browser's `Accept-Language`, else English. CSS
uses logical properties only, so Arabic mirrors the layout automatically.

## Consequences
Adding text means updating the catalogues; a test fails if a translation is
missing or a compiled file is stale. Data typed by users (room categories,
service names) is not translated.
