# Read-only JSON API (v1)

Other programs (a spreadsheet, a dashboard, a script) can read the hotel's
data over HTTP. The API **only reads**: every route answers `GET`, and any
other method gets `405`. Changes are made in the web interface only.

## Tokens

A manager creates a token under **Account → API tokens**, gives it a name
and a lifetime (30, 90 or 365 days), and copies it once. It is never shown
again, because the database stores only its SHA-256 hash.

```
curl -H "Authorization: Bearer hotel_…" https://hotel.lan/api/v1/rooms
```

* A token acts as the manager who created it. It stops working when it
  expires, is revoked, or its owner is deactivated or stops being a manager.
* A manager may have up to 10 active tokens. Creating and revoking them is
  audited.
* The browser's session cookie is **not** accepted on `/api/`, so a web page
  cannot make a signed-in browser call the API.

## Limits

| Who | Limit | Answer when exceeded |
|---|---|---|
| A valid token's owner | 120 calls per minute | `429` with `Retry-After` |
| An address sending wrong tokens | 10 per minute | `429` with `Retry-After` |

## Conventions

* JSON in UTF-8. Dates use `YYYY-MM-DD`; instants use ISO 8601 with an offset.
* Amounts are **integers in millimes** (1 DT = 1000 millimes), in fields
  ending in `_millimes`. Rates are in basis points (`2500` = 25.00 %).
* Errors:

| Status | Body | Meaning |
|---|---|---|
| 400 | `{"error": "invalid_parameter", "parameter": "arrival"}` | A query parameter is missing or malformed |
| 400 | `{"error": "reservation.arrival_in_past", "details": {…}}` | A business rule, same codes as the interface |
| 401 | `{"error": "unauthorized"}` | Missing, wrong, expired or revoked token |
| 403 | `{"error": "forbidden"}` | The owner's role does not allow it |
| 404 | `{"error": "not_found"}` | No such record |
| 429 | `{"error": "too_many_requests"}` | See limits |

## Endpoints

| Path | Parameters | Returns |
|---|---|---|
| `/api/v1/` | – | Version and endpoint list |
| `/api/v1/rooms` | – | Every room: number, category, capacity, `nightly_rate_millimes`, `in_service`, `tonight` (AVAILABLE, RESERVED, OCCUPIED, MAINTENANCE, OUT_OF_SERVICE), `housekeeping` |
| `/api/v1/availability` | `arrival`, `departure` (required), `guests` (default 1) | Rooms free on every night of the stay |
| `/api/v1/reservations` | `status`, `arriving_from`, `arriving_until`, `page`, `per_page` (≤ 100) | `page`, `pages`, `total`, `reservations` (id, code, status, guest, arrival, departure, nights, created_at) |
| `/api/v1/reservations/<id>` | – | The same, plus `rooms` and `accommodation_millimes` |
| `/api/v1/reports/summary` | `first`, `last` (≤ 731 nights) | Nights sold and sellable, occupancy, ADR, RevPAR, revenue, cash received, reservations made, cancellations, no-shows, outstanding |

Example:

```
GET /api/v1/availability?arrival=2026-12-24&departure=2026-12-27&guests=2

{"arrival": "2026-12-24", "departure": "2026-12-27",
 "rooms": [{"id": 3, "number": "101", "category": "Standard", "capacity": 2,
            "nightly_rate_millimes": 120000}]}
```

Reservations contain the guest's name (personal data): give tokens only to
programs that need it, and choose short lifetimes.
