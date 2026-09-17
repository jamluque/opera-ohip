from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

events_received = Counter("ohip_events_received_total", "Events received from OHIP")
events_published = Counter("ohip_events_published_total", "Events published to SQS")
events_consumed = Counter("ohip_events_consumed_total", "Events consumed from SQS")
events_processed = Counter("ohip_events_processed_total", "Events persisted successfully")
events_failed = Counter("ohip_events_failed_total", "Events failed permanently or retried")
events_enriched = Counter("ohip_events_enriched_total", "Events enriched successfully")
events_deduplicated = Counter("ohip_events_deduplicated_total", "Completed events skipped")
websocket_reconnects = Counter("ohip_websocket_reconnects_total", "OHIP websocket reconnects")
oauth_refreshes = Counter("ohip_oauth_refreshes_total", "OAuth token refreshes")
database_writes = Counter("ohip_database_writes_total", "Database writes")
s3_writes = Counter("ohip_s3_writes_total", "S3 raw writes")
ohip_api_calls = Counter("ohip_api_calls_total", "OHIP Property API calls")
ohip_http_errors = Counter(
    "ohip_http_errors_total",
    "OHIP HTTP errors by status code",
    labelnames=("status_code",),
)
messages_retried = Counter("ohip_messages_retried_total", "SQS messages left for retry")
messages_sent_to_dlq = Counter("ohip_messages_sent_to_dlq_total", "SQS messages sent to DLQ")
unresolvable_identifiers = Counter(
    "ohip_unresolvable_identifiers_total",
    "Events whose resource identifier could not be resolved",
)
processing_seconds = Histogram("ohip_event_processing_seconds", "Event processing latency")
ohip_latency_seconds = Histogram("ohip_api_latency_seconds", "OHIP Property API latency")
enrichment_seconds = Histogram("ohip_enrichment_seconds", "Total enrichment latency")
last_event_timestamp = Gauge(
    "ohip_last_event_timestamp_seconds",
    "Unix timestamp of last processed event",
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)
