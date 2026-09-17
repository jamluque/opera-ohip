from pydantic import SecretStr

from ohip_bridge.config import Settings
from ohip_bridge.enrichment_service import OperaEnrichmentService
from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolver


def settings() -> Settings:
    return Settings(
        ohip_gateway_url="https://ohip.example.com",
        ohip_streaming_ws_url="wss://ohip.example.com/subscriptions",
        ohip_token_url="https://ohip.example.com/oauth/token",
        ohip_application_key=SecretStr("app-key"),
        ohip_client_id=SecretStr("client-id"),
        ohip_client_secret=SecretStr("client-secret"),
        ohip_enterprise_id="ENT",
        ohip_scope="scope",
        ohip_chain_code="CHAIN",
        ohip_external_system_code="AWS_BYOD",
        sqs_events_queue_url="https://sqs.eu-west-1.amazonaws.com/123456789012/queue",
        raw_bucket="raw-bucket",
        database_url=SecretStr("postgresql://user:pass@localhost:5432/db"),
    )


def test_service_builds_pool_with_configured_size() -> None:
    s = settings()
    svc = OperaEnrichmentService(
        settings=s,
        router=EventRouter([], {}),
        resolver=IdentifierResolver(),
        ohip_client=None,
    )
    assert svc._pool.max_size == s.enricher_pool_max_size
