from __future__ import annotations

import json
import logging
from typing import Any

import boto3

from ohip_bridge import metrics
from ohip_bridge.config import Settings
from ohip_bridge.events import OhipEvent, stable_json

logger = logging.getLogger(__name__)


class SqsPublisher:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client("sqs", region_name=settings.aws_region)

    def publish(self, event: OhipEvent) -> None:
        body = stable_json(
            {
                "unique_event_id": event.unique_event_id,
                "hotel_id": event.hotel_id,
                "module": event.module,
                "action_type": event.action_type,
                "occurred_at": event.occurred_at.isoformat(),
                "offset": event.offset,
                "payload": event.payload,
            }
        )
        self.client.send_message(
            QueueUrl=self.settings.sqs_events_queue_url,
            MessageBody=body,
            MessageGroupId=event.hotel_id or self.settings.sqs_message_group_id,
            MessageDeduplicationId=event.fifo_deduplication_id,
            MessageAttributes={
                "hotel_id": {"DataType": "String", "StringValue": event.hotel_id},
                "unique_event_id": {"DataType": "String", "StringValue": event.unique_event_id},
            },
        )
        metrics.events_published.inc()
        logger.info(
            "published event to SQS",
            extra={"_event_id": event.unique_event_id, "_hotel_id": event.hotel_id},
        )


class SqsConsumer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = boto3.client("sqs", region_name=settings.aws_region)

    def receive(self) -> list[dict[str, Any]]:
        response = self.client.receive_message(
            QueueUrl=self.settings.sqs_events_queue_url,
            MaxNumberOfMessages=self.settings.sqs_max_messages,
            WaitTimeSeconds=self.settings.sqs_wait_time_seconds,
            VisibilityTimeout=self.settings.sqs_visibility_timeout,
            MessageAttributeNames=["All"],
            AttributeNames=["All"],
        )
        return response.get("Messages", [])

    def delete(self, receipt_handle: str) -> None:
        self.client.delete_message(
            QueueUrl=self.settings.sqs_events_queue_url,
            ReceiptHandle=receipt_handle,
        )

    @staticmethod
    def parse_message(message: dict[str, Any]) -> dict[str, Any]:
        return json.loads(message["Body"])
