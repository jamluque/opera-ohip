from __future__ import annotations

import logging
from datetime import UTC, datetime

import boto3

from ohip_bridge import metrics
from ohip_bridge.config import Settings
from ohip_bridge.events import OhipEvent, stable_json

logger = logging.getLogger(__name__)


class RawEventStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def write(self, event: OhipEvent) -> str:
        key = f"{self.settings.raw_prefix.rstrip('/')}/{event.raw_key_suffix}"
        body = stable_json(
            {
                "ingested_at": datetime.now(UTC).isoformat(),
                "unique_event_id": event.unique_event_id,
                "hotel_id": event.hotel_id,
                "module": event.module,
                "action_type": event.action_type,
                "occurred_at": event.occurred_at.isoformat(),
                "offset": event.offset,
                "payload": event.payload,
            }
        ).encode("utf-8")
        self.client.put_object(
            Bucket=self.settings.raw_bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        metrics.s3_writes.inc()
        logger.info(
            "wrote raw event to S3",
            extra={"s3_key": key, "_event_id": event.unique_event_id},
        )
        return key
