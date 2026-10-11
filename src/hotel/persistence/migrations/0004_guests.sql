-- Sprint 2: guests.

CREATE TABLE guest (
    id                 INTEGER PRIMARY KEY,
    first_name         TEXT    NOT NULL CHECK (length(first_name) BETWEEN 1 AND 60),
    last_name          TEXT    NOT NULL CHECK (length(last_name) BETWEEN 1 AND 60),
    -- Accent-free, lower-case copies used for searching and sorting.
    search_name        TEXT    NOT NULL,
    sort_name          TEXT    NOT NULL,
    id_doc_type        TEXT    NOT NULL CHECK (id_doc_type IN ('CIN', 'PASSPORT')),
    id_doc_number      TEXT    NOT NULL CHECK (length(id_doc_number) BETWEEN 5 AND 20),
    nationality        TEXT    CHECK (nationality IS NULL OR length(nationality) = 2),
    phone              TEXT,
    phone_digits       TEXT,
    email              TEXT    CHECK (email IS NULL OR length(email) <= 254),
    notes              TEXT    NOT NULL DEFAULT '' CHECK (length(notes) <= 500),
    is_vip             INTEGER NOT NULL DEFAULT 0 CHECK (is_vip IN (0, 1)),
    do_not_rent        INTEGER NOT NULL DEFAULT 0 CHECK (do_not_rent IN (0, 1)),
    do_not_rent_reason TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at         TEXT    NOT NULL,
    version            INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    UNIQUE (id_doc_type, id_doc_number),  -- business rule BR2
    CHECK (do_not_rent = 0 OR length(do_not_rent_reason) > 0)
);
CREATE INDEX ix_guest_search_name ON guest (search_name);
CREATE INDEX ix_guest_sort_name ON guest (sort_name);
CREATE INDEX ix_guest_phone_digits ON guest (phone_digits);
CREATE INDEX ix_guest_email ON guest (email);
