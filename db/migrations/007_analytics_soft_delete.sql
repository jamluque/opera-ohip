ALTER TABLE opera_analytics.reservation_daily_snapshot ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE opera_analytics.reservation_last_status_daily ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
