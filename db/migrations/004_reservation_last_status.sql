CREATE SCHEMA IF NOT EXISTS opera_analytics;

CREATE TABLE IF NOT EXISTS opera_analytics.reservation_last_status_daily (
    snapshot_date DATE NOT NULL,
    snapshot_taken_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hotel_id TEXT NOT NULL,
    reservation_id TEXT NOT NULL,
    confirmation_no TEXT,
    arrival_date DATE,
    departure_date DATE,
    last_status TEXT,
    last_status_event_at TIMESTAMPTZ,
    last_event_id TEXT,
    room_type TEXT,
    rate_code TEXT,
    market_code TEXT,
    source_code TEXT,
    channel_code TEXT,
    source_updated_at TIMESTAMPTZ,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_date, hotel_id, reservation_id)
);

CREATE INDEX IF NOT EXISTS reservation_last_status_daily_status_idx
    ON opera_analytics.reservation_last_status_daily (
        snapshot_date,
        hotel_id,
        last_status
    );

CREATE INDEX IF NOT EXISTS reservation_last_status_daily_arrival_idx
    ON opera_analytics.reservation_last_status_daily (
        hotel_id,
        arrival_date,
        snapshot_date
    );

CREATE INDEX IF NOT EXISTS reservation_last_status_daily_segment_idx
    ON opera_analytics.reservation_last_status_daily (
        snapshot_date,
        hotel_id,
        market_code,
        channel_code,
        source_code
    );

CREATE OR REPLACE VIEW opera_analytics.v_reservation_last_status_current AS
SELECT
    snapshot_date,
    snapshot_taken_at,
    hotel_id,
    reservation_id,
    confirmation_no,
    arrival_date,
    departure_date,
    last_status,
    last_status_event_at,
    last_event_id,
    room_type,
    rate_code,
    market_code,
    source_code,
    channel_code,
    source_updated_at
FROM opera_analytics.reservation_last_status_daily
WHERE snapshot_date = CURRENT_DATE;
