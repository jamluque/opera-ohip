from __future__ import annotations

import asyncio

from ohip_bridge.config import get_bootstrap_settings, get_settings
from ohip_bridge.enrichment_service import OperaEnrichmentService
from ohip_bridge.event_router import EventRouter
from ohip_bridge.health import health_state, start_health_server
from ohip_bridge.identifier_resolver import IdentifierResolver
from ohip_bridge.logging import configure_logging
from ohip_bridge.metrics import start_metrics_server
from ohip_bridge.ohip_client import OAuthTokenProvider, OHIPClient
from ohip_bridge.opera_event_parser import OperaEventParser
from ohip_bridge.secrets import load_secret_into_environment
from ohip_bridge.sqs import SqsConsumer
from ohip_bridge.sqs_message_processor import SQSMessageProcessor


async def run() -> None:
    bootstrap = get_bootstrap_settings()
    load_secret_into_environment(bootstrap.ohip_secret_id, bootstrap.aws_region)
    get_settings.cache_clear()
    settings = get_settings()
    configure_logging(settings.log_level)
    start_health_server(settings.health_port)
    start_metrics_server(settings.metrics_port)

    token_provider = OAuthTokenProvider(settings)
    ohip_client = OHIPClient(settings, token_provider)
    router = EventRouter.from_yaml(settings.enricher_router_config)
    service = OperaEnrichmentService(
        settings=settings,
        router=router,
        resolver=IdentifierResolver(),
        ohip_client=ohip_client,
    )
    processor = SQSMessageProcessor(settings, SqsConsumer(settings), OperaEventParser(), service)
    service._pool.open()
    health_state.set_ready(True, component="event-enricher")
    try:
        await processor.run_forever()
    finally:
        await ohip_client.close()
        service._pool.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
