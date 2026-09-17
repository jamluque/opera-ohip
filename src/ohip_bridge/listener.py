from __future__ import annotations

import asyncio
import logging
import random
import time

from ohip_bridge import metrics
from ohip_bridge.config import get_bootstrap_settings, get_settings
from ohip_bridge.events import parse_ohip_event
from ohip_bridge.graphql import OhipStreamingClient
from ohip_bridge.health import health_state, start_health_server
from ohip_bridge.logging import configure_logging
from ohip_bridge.oauth import OAuthClient
from ohip_bridge.offsets import S3OffsetStore
from ohip_bridge.secrets import load_secret_into_environment
from ohip_bridge.sqs import SqsPublisher

logger = logging.getLogger(__name__)


async def run() -> None:
    bootstrap = get_bootstrap_settings()
    load_secret_into_environment(bootstrap.ohip_secret_id, bootstrap.aws_region)
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.log_level)
    start_health_server(settings.health_port)
    metrics.start_metrics_server(settings.metrics_port)

    oauth = OAuthClient(settings)
    client = OhipStreamingClient(settings, oauth)
    publisher = SqsPublisher(settings)
    offsets = S3OffsetStore(settings)
    delay = settings.ohip_reconnect_min_seconds
    health_state.set_ready(True, component="listener")

    while True:
        try:
            offset = offsets.load(settings.ohip_subscription_name)
            logger.info("connecting to OHIP Streaming API", extra={"offset": offset})
            async for raw_event in client.events(offset):
                event = parse_ohip_event(raw_event)
                metrics.events_received.inc()
                publisher.publish(event)
                offsets.save(settings.ohip_subscription_name, event.offset, event.unique_event_id)
                metrics.last_event_timestamp.set(time.time())
                delay = settings.ohip_reconnect_min_seconds
        except Exception:
            metrics.websocket_reconnects.inc()
            logger.exception(
                "OHIP listener disconnected; reconnecting",
                extra={"delay_seconds": delay},
            )
            jitter = random.uniform(0, min(delay, 5))
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2, settings.ohip_reconnect_max_seconds)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
