CREATE INDEX IF NOT EXISTS reservation_daily_snapshot_last_status_refresh_idx
    ON opera_analytics.reservation_daily_snapshot (
        snapshot_date,
        hotel_id,
        reservation_id,
        last_event_at DESC,
        stay_date
    );
