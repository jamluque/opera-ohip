ALTER TABLE opera_core.reservation ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE opera_core.profile ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE opera_core.folio ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE opera_core.folio_transaction ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
