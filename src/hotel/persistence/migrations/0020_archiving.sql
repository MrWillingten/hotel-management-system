-- Sprint 6 (story 6.17): delete or archive. A record that was never used
-- can be deleted; one with history is archived instead: hidden from lists,
-- forms and suggestions, its history (stays, invoices, audit log) kept, and
-- restorable. NULL = not archived.
ALTER TABLE guest ADD COLUMN archived_at TEXT;
ALTER TABLE room ADD COLUMN archived_at TEXT;
ALTER TABLE extra ADD COLUMN archived_at TEXT;
ALTER TABLE tax_rule ADD COLUMN archived_at TEXT;
ALTER TABLE app_user ADD COLUMN archived_at TEXT;
