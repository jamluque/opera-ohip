from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from ohip_bridge import metrics
from ohip_bridge.config import get_bootstrap_settings, get_settings
from ohip_bridge.db import EventRepository
from ohip_bridge.events import OhipEvent
from ohip_bridge.health import health_state, start_health_server
from ohip_bridge.logging import configure_logging
from ohip_bridge.raw_store import RawEventStore
from ohip_bridge.secrets import load_secret_into_environment
from ohip_bridge.sqs import SqsConsumer

logger = logging.getLogger(__name__)


def _event_from_message(payload: dict) -> OhipEvent:
    return OhipEvent(
        unique_event_id=payload["unique_event_id"],
        hotel_id=payload["hotel_id"],
        module=payload.get("module"),
        action_type=payload.get("action_type"),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]).astimezone(UTC),
        payload=payload["payload"],
        offset=payload.get("offset"),
    )


def run() -> None:
    bootstrap = get_bootstrap_settings()
    load_secret_into_environment(bootstrap.ohip_secret_id, bootstrap.aws_region)
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.log_level)
    start_health_server(settings.health_port)
    metrics.start_metrics_server(settings.metrics_port)

    sqs = SqsConsumer(settings)
    raw_store = RawEventStore(settings)
    repository = EventRepository(settings)
    health_state.set_ready(True, component="consumer")

    while True:
        messages = sqs.receive()
        if not messages:
            time.sleep(settings.consumer_idle_sleep_seconds)
            continue
        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            with metrics.processing_seconds.time():
                try:
                    payload = SqsConsumer.parse_message(message)
                    event = _event_from_message(payload)
                    metrics.events_consumed.inc()
                    raw_s3_key = raw_store.write(event)
                    repository.persist_event(
                        unique_event_id=event.unique_event_id,
                        hotel_id=event.hotel_id,
                        module=event.module,
                        action_type=event.action_type,
                        occurred_at=event.occurred_at,
                        raw_s3_key=raw_s3_key,
                        payload=event.payload,
                        offset=event.offset,
                    )
                    sqs.delete(receipt_handle)
                    metrics.events_processed.inc()
                    metrics.last_event_timestamp.set(time.time())
                except Exception:
                    metrics.events_failed.inc()
                    logger.exception("failed to process SQS message; message will be retried")


def main() -> None:
    run()


if __name__ == "__main__":
    main()
