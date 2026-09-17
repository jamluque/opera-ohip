from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import AnyUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BootstrapSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    aws_region: str = "eu-west-1"
    ohip_secret_id: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    aws_region: str = "eu-west-1"
    metrics_port: int = 9100
    health_port: int = 8080

    ohip_secret_id: str | None = None
    ohip_gateway_url: AnyUrl
    ohip_streaming_ws_url: str
    ohip_token_url: AnyUrl
    ohip_application_key: SecretStr
    ohip_client_id: SecretStr
    ohip_client_secret: SecretStr
    ohip_enterprise_id: str
    ohip_scope: str
    ohip_chain_code: str
    ohip_hotel_ids: Annotated[list[str], Field(default_factory=list)]
    ohip_external_system_code: str
    ohip_subscription_name: str = "opera-ohip-business-events"
    ohip_subscription_query_file: str | None = None
    ohip_reconnect_min_seconds: int = 1
    ohip_reconnect_max_seconds: int = 60
    ohip_ping_interval_seconds: int = 15
    ohip_token_refresh_skew_seconds: int = 120

    sqs_events_queue_url: str
    sqs_message_group_id: str = "opera-ohip-stream"
    sqs_dedup_window_seconds: int = 300
    sqs_wait_time_seconds: int = 20
    sqs_max_messages: int = 10
    sqs_visibility_timeout: int = 120
    consumer_idle_sleep_seconds: int = 2

    enricher_router_config: str = "config/event-router.yaml"
    enricher_max_attempts: int = 5
    sqs_enricher_dlq_url: str | None = None
    cloudwatch_metrics_namespace: str = "Opera/OHIP/Enrichment"
    cloudwatch_metrics_enabled: bool = True

    raw_bucket: str
    raw_prefix: str = "ohip/events"
    offset_prefix: str = "ohip/offsets"

    database_url: SecretStr

    @field_validator("ohip_hotel_ids", mode="before")
    @classmethod
    def _split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_bootstrap_settings() -> BootstrapSettings:
    return BootstrapSettings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
