-- Sprint 6 (story 6.14): the walk-through for new accounts. One row per user
-- once they finished or skipped the tour, or hid the "Getting started" list.
-- The list's ticks themselves are not stored: they are read from the audit log.
CREATE TABLE onboarding (
    user_id                INTEGER PRIMARY KEY REFERENCES app_user (id) ON DELETE CASCADE,
    tour_done_at           TEXT,
    checklist_dismissed_at TEXT
);
