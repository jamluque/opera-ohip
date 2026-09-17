from __future__ import annotations

import asyncio
import logging
from typing import Any

import boto3

from ohip_bridge import metrics
from ohip_bridge.cloudwatch_metrics import CloudWatchMetrics, MetricPoint
from ohip_bridge.config import Settings
from ohip_bridge.enrichment_service import (
    EnrichmentPoisonError,
    EnrichmentRetryableError,
    OperaEnrichmentService,
)
from ohip_bridge.opera_event_parser import OperaEventParser
from ohip_bridge.sqs import SqsConsumer

logger = logging.getLogger(__name__)


class SQSMessageProcessor:
    def __init__(
        self,
        settings: Settings,
        sqs: SqsConsumer,
        parser: OperaEventParser,
        service: OperaEnrichmentService,
    ) -> None:
        self.settings = settings
        self.sqs = sqs
        self.parser = parser
        self.service = service
        self.client = boto3.client("sqs", region_name=settings.aws_region)
        self.cloudwatch = (
            CloudWatchMetrics(settings.cloudwatch_metrics_namespace, settings.aws_region)
            if settings.cloudwatch_metrics_enabled
            else None
        )

    async def process_message(self, message: dict[str, Any]) -> bool:
        receipt_handle = message["ReceiptHandle"]
        payload = SqsConsumer.parse_message(message)
        event = self.parser.parse(payload)
        receive_count = int(message.get("Attributes", {}).get("ApproximateReceiveCount", "1"))
        try:
            result = await self.service.enrich(event)
        except EnrichmentRetryableError as exc:
            self._change_visibility(receipt_handle, exc.retry_after)
            self._metric("MessagesRetried")
            return False
        except EnrichmentPoisonError as exc:
            self.service.mark_failed(event, "FAILED", str(exc))
            if receive_count >= self.settings.enricher_max_attempts:
                self._send_to_dlq(message, str(exc))
                self.sqs.delete(receipt_handle)
                metrics.messages_sent_to_dlq.inc()
                self._metric("MessagesSentToDLQ")
                return True
            return False
        except Exception:
            logger.exception("failed before deleting SQS message")
            return False
        self.sqs.delete(receipt_handle)
        self._metric("EventsDeduplicated" if result.deduplicated else "EventsProcessed")
        return True

    async def run_forever(self) -> None:
        while True:
            messages = self.sqs.receive()
            if not messages:
                await asyncio.sleep(self.settings.consumer_idle_sleep_seconds)
                continue
            for message in messages:
                with metrics.enrichment_seconds.time():
                    await self.process_message(message)

    def _metric(self, name: str, value: float = 1, unit: str = "Count") -> None:
        if self.cloudwatch:
            self.cloudwatch.put(MetricPoint(name, value, unit))

    def _change_visibility(self, receipt_handle: str, retry_after: int | None) -> None:
        timeout = retry_after or self.settings.sqs_visibility_timeout
        self.client.change_message_visibility(
            QueueUrl=self.settings.sqs_events_queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=min(timeout, 43200),
        )

    def _send_to_dlq(self, message: dict[str, Any], reason: str) -> None:
        if not self.settings.sqs_enricher_dlq_url:
            return
        self.client.send_message(
            QueueUrl=self.settings.sqs_enricher_dlq_url,
            MessageBody=message["Body"],
            MessageGroupId="opera-ohip-enricher-poison",
            MessageDeduplicationId=f"poison-{message.get('MessageId', '')}",
            MessageAttributes={
                "failure_reason": {"DataType": "String", "StringValue": reason[:256]},
            },
        )
