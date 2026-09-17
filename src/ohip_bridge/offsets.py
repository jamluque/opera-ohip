from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from ohip_bridge.config import Settings

logger = logging.getLogger(__name__)


class S3OffsetStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client("s3", region_name=settings.aws_region)

    def _key(self, subscription_name: str) -> str:
        return f"{self.settings.offset_prefix.rstrip('/')}/{subscription_name}.json"

    def load(self, subscription_name: str) -> dict[str, Any] | None:
        try:
            response = self.client.get_object(
                Bucket=self.settings.raw_bucket,
                Key=self._key(subscription_name),
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404"}:
                return None
            raise
        return json.loads(response["Body"].read().decode("utf-8"))

    def save(self, subscription_name: str, offset: str | None, event_id: str) -> None:
        payload = {
            "subscription_name": subscription_name,
            "offset": offset,
            "last_unique_event_id": event_id,
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self.client.put_object(
            Bucket=self.settings.raw_bucket,
            Key=self._key(subscription_name),
            Body=json.dumps(payload, sort_keys=True).encode("utf-8"),
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )
        logger.info("saved listener offset", extra={"offset": offset, "_event_id": event_id})
