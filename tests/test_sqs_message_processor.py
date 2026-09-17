import json

import pytest

from ohip_bridge.enrichment_service import EnrichmentResult
from ohip_bridge.opera_event_parser import OperaEventParser
from ohip_bridge.sqs_message_processor import SQSMessageProcessor


class FakeSqs:
    def __init__(self) -> None:
        self.deleted = []

    def delete(self, receipt_handle: str) -> None:
        self.deleted.append(receipt_handle)


class FakeService:
    async def enrich(self, event):
        return EnrichmentResult(event.unique_event_id, "COMPLETED")

    def mark_failed(self, event, status, error_message):
        pass


class FailingService(FakeService):
    async def enrich(self, event):
        raise RuntimeError("database down before commit")


class Settings:
    aws_region = "eu-west-1"
    cloudwatch_metrics_namespace = "Opera/OHIP/Enrichment"
    cloudwatch_metrics_enabled = False
    sqs_events_queue_url = "queue-url"
    sqs_enricher_dlq_url = None
    sqs_visibility_timeout = 120
    enricher_max_attempts = 5


@pytest.mark.asyncio
async def test_repeated_sqs_message_is_deleted_after_completed_dedup() -> None:
    sqs = FakeSqs()
    processor = SQSMessageProcessor(Settings(), sqs, OperaEventParser(), FakeService())  # type: ignore[arg-type]
    message = {
        "ReceiptHandle": "rh-1",
        "Body": json.dumps(
            {
                "uniqueEventId": "evt-1",
                "hotelId": "MAD01",
                "moduleName": "Profile",
                "eventName": "Update",
                "primaryKey": "p1",
            }
        ),
        "Attributes": {"ApproximateReceiveCount": "2"},
    }

    processed = await processor.process_message(message)

    assert processed is True
    assert sqs.deleted == ["rh-1"]


@pytest.mark.asyncio
async def test_postgres_failure_before_delete_keeps_sqs_message() -> None:
    sqs = FakeSqs()
    processor = SQSMessageProcessor(Settings(), sqs, OperaEventParser(), FailingService())  # type: ignore[arg-type]
    message = {
        "ReceiptHandle": "rh-2",
        "Body": json.dumps(
            {
                "uniqueEventId": "evt-2",
                "hotelId": "MAD01",
                "moduleName": "Profile",
                "eventName": "Update",
                "primaryKey": "p1",
            }
        ),
        "Attributes": {"ApproximateReceiveCount": "1"},
    }

    processed = await processor.process_message(message)

    assert processed is False
    assert sqs.deleted == []
