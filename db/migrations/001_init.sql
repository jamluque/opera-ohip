CREATE TABLE IF NOT EXISTS ohip_events (
    id BIGSERIAL PRIMARY KEY,
    unique_event_id TEXT NOT NULL,
    hotel_id TEXT NOT NULL,
    module TEXT,
    action_type TEXT,
    occurred_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_s3_key TEXT NOT NULL,
    stream_offset TEXT,
    payload JSONB NOT NULL,
    CONSTRAINT ohip_events_unique_event_id_uk UNIQUE (unique_event_id)
);

CREATE INDEX IF NOT EXISTS ohip_events_hotel_occurred_idx
    ON ohip_events (hotel_id, occurred_at DESC);

CREATE INDEX IF NOT EXISTS ohip_events_module_action_idx
    ON ohip_events (module, action_type);

CREATE INDEX IF NOT EXISTS ohip_events_payload_gin_idx
    ON ohip_events USING GIN (payload);
