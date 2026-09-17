CREATE SCHEMA IF NOT EXISTS opera_events;
CREATE SCHEMA IF NOT EXISTS opera_raw;
CREATE SCHEMA IF NOT EXISTS opera_core;

CREATE TABLE IF NOT EXISTS opera_events.event (
    id BIGSERIAL PRIMARY KEY,
    unique_event_id TEXT NOT NULL,
    chain_code TEXT,
    hotel_id TEXT NOT NULL,
    stream_offset TEXT,
    primary_key TEXT,
    module_name TEXT,
    event_name TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    payload JSONB NOT NULL,
    CONSTRAINT opera_event_unique_event_id_uk UNIQUE (unique_event_id),
    CONSTRAINT opera_event_status_ck CHECK (
        status IN ('RECEIVED', 'COMPLETED', 'FAILED', 'RETRYABLE', 'DELETED')
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS opera_event_chain_offset_uk
    ON opera_events.event (chain_code, stream_offset)
    WHERE chain_code IS NOT NULL AND stream_offset IS NOT NULL;

CREATE INDEX IF NOT EXISTS opera_event_status_idx
    ON opera_events.event (status, received_at);

CREATE TABLE IF NOT EXISTS opera_raw.resource_snapshot (
    id BIGSERIAL PRIMARY KEY,
    unique_event_id TEXT NOT NULL REFERENCES opera_events.event (unique_event_id),
    hotel_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL,
    CONSTRAINT opera_raw_snapshot_event_resource_uk UNIQUE (
        unique_event_id, resource_type, resource_id
    )
);

CREATE INDEX IF NOT EXISTS opera_raw_snapshot_resource_idx
    ON opera_raw.resource_snapshot (resource_type, resource_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS opera_core.reservation (
    hotel_id TEXT NOT NULL,
    reservation_id TEXT NOT NULL,
    confirmation_no TEXT,
    arrival_date DATE,
    departure_date DATE,
    reservation_status TEXT,
    source_updated_at TIMESTAMPTZ,
    last_event_id TEXT NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hotel_id, reservation_id)
);

CREATE TABLE IF NOT EXISTS opera_core.profile (
    profile_id TEXT PRIMARY KEY,
    profile_type TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    source_updated_at TIMESTAMPTZ,
    last_event_id TEXT NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS opera_core.folio (
    hotel_id TEXT NOT NULL,
    reservation_id TEXT NOT NULL,
    folio_id TEXT NOT NULL,
    folio_no TEXT,
    balance_amount NUMERIC(18, 4),
    currency_code TEXT,
    source_updated_at TIMESTAMPTZ,
    last_event_id TEXT NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hotel_id, reservation_id, folio_id)
);

CREATE TABLE IF NOT EXISTS opera_core.folio_transaction (
    hotel_id TEXT NOT NULL,
    transaction_no TEXT NOT NULL,
    reservation_id TEXT,
    folio_id TEXT,
    amount NUMERIC(18, 4),
    currency_code TEXT,
    transaction_code TEXT,
    source_updated_at TIMESTAMPTZ,
    last_event_id TEXT NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (hotel_id, transaction_no)
);
