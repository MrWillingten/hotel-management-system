-- Sprint 4 (story 4.9): housekeeping goes dirty -> cleaned -> inspected.
-- 0007 stored only CLEAN / DIRTY and SQLite cannot change a CHECK in place,
-- so a cleaned room still waiting for its inspection gets a flag instead:
--   DIRTY                         to clean
--   CLEAN + awaiting_inspection   cleaned, waiting for the inspection
--   CLEAN, not awaiting           inspected: ready for the next guest
ALTER TABLE room ADD COLUMN awaiting_inspection INTEGER NOT NULL DEFAULT 0
    CHECK (awaiting_inspection IN (0, 1) AND (awaiting_inspection = 0 OR housekeeping = 'CLEAN'));
