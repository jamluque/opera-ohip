from datetime import UTC, datetime
from types import SimpleNamespace

from ohip_bridge.events import OhipEvent
from ohip_bridge.sqs import SqsPublisher


class FakeSqsClient:
    def __init__(self) -> None:
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return {"MessageId": "msg-1"}


def test_publish_uses_fifo_group_and_unique_event_for_dedup(monkeypatch) -> None:
    fake_client = FakeSqsClient()
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: fake_client)
    settings = SimpleNamespace(
        aws_region="eu-west-1",
        sqs_events_queue_url="https://sqs.example/events.fifo",
        sqs_message_group_id="opera-ohip-stream",
    )
    publisher = SqsPublisher(settings)  # type: ignore[arg-type]
    event = OhipEvent(
        unique_event_id="evt-123",
        hotel_id="MAD01",
        module="Reservation",
        action_type="NEW RESERVATION",
        occurred_at=datetime(2026, 8, 3, tzinfo=UTC),
        payload={"uniqueEventId": "evt-123"},
        offset="42",
    )

    publisher.publish(event)

    call = fake_client.calls[0]
    assert call["QueueUrl"] == "https://sqs.example/events.fifo"
    assert call["MessageGroupId"] == "opera-ohip-stream"
    assert call["MessageDeduplicationId"] == "evt-123"
    assert call["MessageAttributes"]["hotel_id"]["StringValue"] == "MAD01"
