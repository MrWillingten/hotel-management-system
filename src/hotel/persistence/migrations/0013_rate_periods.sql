-- Sprint 5 (story 5.6): seasonal prices per room category.
-- [start_date, end_date) like maintenance: end_date is the day after the last night.
CREATE TABLE rate_period (
    id          INTEGER PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES room_category (id),
    name        TEXT    NOT NULL CHECK (length(name) BETWEEN 1 AND 60),
    start_date  TEXT    NOT NULL,
    end_date    TEXT    NOT NULL,
    rate_mill   INTEGER NOT NULL CHECK (rate_mill > 0),
    created_at  TEXT    NOT NULL,
    CHECK (end_date > start_date)
);
CREATE INDEX ix_rate_period_category ON rate_period (category_id, start_date);
