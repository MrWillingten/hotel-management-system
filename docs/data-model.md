# Data model

The schema grows sprint by sprint through numbered migrations
(`src/hotel/persistence/migrations/NNNN_*.sql`). Tables marked ✅ exist today;
the others are the target design.

## Conceptual ERD

```mermaid
erDiagram
    ROOM_CATEGORY ||--o{ ROOM : classifies
    ROOM ||--o{ MAINTENANCE : "is closed by"
    ROOM ||--o{ ROOM_NIGHT : "is occupied on"
    GUEST ||--o{ RESERVATION : makes
    RESERVATION ||--|{ RESERVATION_ROOM : includes
    ROOM ||--o{ RESERVATION_ROOM : "is booked in"
    RESERVATION ||--o{ ROOM_NIGHT : holds
    MAINTENANCE ||--o{ ROOM_NIGHT : blocks
    RESERVATION ||--o{ SERVICE_CHARGE : accrues
    SERVICE ||--o{ SERVICE_CHARGE : "is billed as"
    RESERVATION ||--o{ PAYMENT : receives
    RESERVATION ||--o{ DISCOUNT : "is granted"
    RESERVATION ||--o| INVOICE : "is closed by"
    INVOICE ||--|{ INVOICE_LINE : contains
    APP_USER ||--o{ USER_SESSION : "signs in with"
    APP_USER ||--o{ AUDIT_LOG : performs
    APP_USER ||--o{ RESERVATION : creates
```

`TAX_RULE`, `SETTING`, `COUNTER` and `LOGIN_FAILURE` stand alone. Invoices copy
tax values instead of referencing `TAX_RULE`, so changing a rate never alters an
issued invoice.

## Relational schema

Notation: `PK` primary key · `FK` foreign key · `UQ` unique · `CK` check ·
`_mill` = millimes (INTEGER) · `_bp` = basis points (700 = 7.00 %).

```
✅ app_user(id PK, username UQ CK 3..32, full_name CK 1..100, password_hash,
            role CK∈{RECEPTIONIST,MANAGER}, is_active, must_change_password,
            failed_attempts CK≥0, locked_until, created_at, version)
✅ user_session(token_hash PK CK len=64, user_id FK→app_user ON DELETE CASCADE,
                created_at, last_seen_at, expires_at, ip, user_agent)
✅ login_failure(id PK, ip, username, at)          INDEX (ip, at)

✅ room_category(id PK, name UQ, description)
✅ room(id PK, number UQ, category_id FK, capacity CK>0, nightly_rate_mill CK≥0,
        in_service, notes, version)
✅ maintenance(id PK, room_id FK, start_date, end_date, reason, created_by FK,
               CK end_date > start_date)
✅ guest(id PK, first_name, last_name, id_doc_type CK∈{CIN,PASSPORT}, id_doc_number,
         nationality, phone, email, is_vip, do_not_rent, notes, is_active, created_at,
         version, UQ(id_doc_type, id_doc_number))
✅ reservation(id PK, code UQ, guest_id FK, arrival, departure,
               status CK∈{CONFIRMED,CHECKED_IN,CHECKED_OUT,CANCELLED,NO_SHOW},
               cancellation_fee_mill, created_by FK, created_at, checked_in_at,
               checked_out_at, cancelled_at, version, CK departure > arrival)
✅ reservation_room(reservation_id FK, room_id FK, adults CK≥1, children CK≥0,
                    PK(reservation_id, room_id))
✅ room_night(room_id FK, night, reservation_id FK NULL, maintenance_id FK NULL,
              rate_mill, PK(room_id, night),
              CK exactly one of reservation_id / maintenance_id is set,
              CK a reserved night has a rate)
   service(id PK, name UQ, unit_price_mill CK≥0, is_active)
   service_charge(id PK, reservation_id FK, service_id FK, quantity CK 1..99,
                  unit_price_mill, charge_date, created_by FK)
   payment(id PK, reservation_id FK, amount_mill CK>0,
           kind CK∈{DEPOSIT,PAYMENT,REFUND}, method CK∈{CASH,CARD,TRANSFER},
           paid_at, recorded_by FK)
   discount(id PK, reservation_id FK, kind CK∈{PERCENT,FIXED}, value, reason NOT NULL,
            approved_by FK, created_at)
   tax_rule(id PK, name, kind CK∈{PERCENT,PER_ADULT_NIGHT}, value,
            applies_to CK∈{ACCOMMODATION,SERVICES}, is_active, valid_from, valid_to)
   invoice(id PK, number UQ, reservation_id FK UQ, issued_at, issued_by FK,
           subtotal_mill, discount_mill, tax_mill, total_mill, paid_mill, balance_mill)
   invoice_line(id PK, invoice_id FK, line_no, kind, description, quantity,
                unit_mill, amount_mill, UQ(invoice_id, line_no))
✅ audit_log(id PK, at, user_id FK NULL, action, entity, entity_id, details, ip,
             prev_hash, hash)
✅ setting(key PK, value)
✅ counter(name, year, value, PK(name, year))                    gap-free invoice numbers
✅ form_token(token_hash PK, user_id FK, created_at) one-time submit tokens
```

## Conventions

* Timestamps: UTC ISO-8601 text **with microseconds**, so they sort correctly as text.
* Calendar dates: `YYYY-MM-DD`.
* Booleans: `INTEGER` 0/1 with a `CHECK`.
* `version` columns implement optimistic locking (`UPDATE … WHERE id = ? AND version = ?`).
* Prices copied at booking time (`rate_mill`, `unit_price_mill`) are deliberate
  denormalisation for historical accuracy.
* `PRAGMA foreign_keys = ON`, `busy_timeout = 5000`, `synchronous = FULL` on every
  connection; `journal_mode = WAL` once per database.
