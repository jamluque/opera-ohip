CREATE SCHEMA IF NOT EXISTS opera_analytics;

CREATE TABLE IF NOT EXISTS opera_analytics.reservation_daily_snapshot (
    snapshot_date DATE NOT NULL,
    snapshot_taken_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hotel_id TEXT NOT NULL,
    stay_date DATE NOT NULL,
    reservation_id TEXT NOT NULL,
    confirmation_no TEXT,
    room_type TEXT,
    rate_code TEXT,
    market_code TEXT,
    source_code TEXT,
    channel_code TEXT,
    reservation_status TEXT,
    rooms NUMERIC(12, 4) NOT NULL DEFAULT 0,
    room_revenue NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_revenue NUMERIC(18, 4) NOT NULL DEFAULT 0,
    adr NUMERIC(18, 4),
    created_date DATE,
    cancelled_date DATE,
    source_updated_at TIMESTAMPTZ,
    last_event_id TEXT,
    last_event_at TIMESTAMPTZ,
    payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (snapshot_date, hotel_id, stay_date, reservation_id)
);

CREATE INDEX IF NOT EXISTS reservation_daily_snapshot_stay_idx
    ON opera_analytics.reservation_daily_snapshot (hotel_id, stay_date, snapshot_date);

CREATE INDEX IF NOT EXISTS reservation_daily_snapshot_segment_idx
    ON opera_analytics.reservation_daily_snapshot (
        snapshot_date,
        hotel_id,
        market_code,
        channel_code,
        source_code
    );

CREATE TABLE IF NOT EXISTS opera_analytics.pickup_metric (
    snapshot_date DATE NOT NULL,
    comparison_days INTEGER NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hotel_id TEXT NOT NULL,
    stay_date DATE NOT NULL,
    market_code TEXT NOT NULL DEFAULT 'UNMAPPED',
    channel_code TEXT NOT NULL DEFAULT 'UNMAPPED',
    source_code TEXT NOT NULL DEFAULT 'UNMAPPED',
    room_type TEXT NOT NULL DEFAULT 'UNMAPPED',
    rate_code TEXT NOT NULL DEFAULT 'UNMAPPED',
    rooms_on_books NUMERIC(18, 4) NOT NULL DEFAULT 0,
    rooms_on_books_previous NUMERIC(18, 4) NOT NULL DEFAULT 0,
    pickup_rooms NUMERIC(18, 4) NOT NULL DEFAULT 0,
    room_revenue_on_books NUMERIC(18, 4) NOT NULL DEFAULT 0,
    room_revenue_previous NUMERIC(18, 4) NOT NULL DEFAULT 0,
    pickup_room_revenue NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_revenue_on_books NUMERIC(18, 4) NOT NULL DEFAULT 0,
    total_revenue_previous NUMERIC(18, 4) NOT NULL DEFAULT 0,
    pickup_total_revenue NUMERIC(18, 4) NOT NULL DEFAULT 0,
    adr_on_books NUMERIC(18, 4),
    pickup_adr NUMERIC(18, 4),
    PRIMARY KEY (
        snapshot_date,
        comparison_days,
        hotel_id,
        stay_date,
        market_code,
        channel_code,
        source_code,
        room_type,
        rate_code
    )
);

CREATE INDEX IF NOT EXISTS pickup_metric_report_idx
    ON opera_analytics.pickup_metric (
        snapshot_date,
        comparison_days,
        hotel_id,
        stay_date
    );
