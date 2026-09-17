import asyncio

import pytest
from botocore.exceptions import EndpointConnectionError

import scripts.perf_streaming_e2e as e2e
from scripts.perf_streaming_e2e import (
    _delete_local_queues,
    count_new_event_ids,
    message_group_id,
    new_report,
)


def test_e2e_report_tracks_infrastructure_boundaries() -> None:
    report = new_report(total_messages=3, seed=7, realtime=False)

    assert report["input"]["total_messages"] == 3
    assert report["input"]["realtime"] is False
    assert report["summary"]["processed_messages"] == 0
    assert report["pipeline"]["stream_extract"]["count"] == 0
    assert report["pipeline"]["sqs_publish"]["count"] == 0
    assert report["pipeline"]["sqs_receive"]["count"] == 0
    assert report["pipeline"]["enrich_persist"]["count"] == 0
    assert report["pipeline"]["analytics_snapshot"]["count"] == 0


def test_message_group_id_is_stable_and_partitioned() -> None:
    first = message_group_id("opera-ohip-stream", 32, "MAD01", "resv-1")
    second = message_group_id("opera-ohip-stream", 32, "MAD01", "resv-1")

    assert first == second
    assert first.startswith("opera-ohip-stream-")
    assert 0 <= int(first.rsplit("-", 1)[1]) < 32


def test_e2e_report_records_optimized_worker_and_batch_config() -> None:
    report = new_report(
        total_messages=3,
        seed=7,
        realtime=False,
        worker_count=8,
        worker_concurrency=4,
        db_batch_size=100,
        sqs_batch_size=10,
        message_group_partitions=32,
    )

    assert report["optimization"] == {
        "worker_count": 8,
        "worker_concurrency": 4,
        "db_batch_size": 100,
        "sqs_batch_size": 10,
        "message_group_partitions": 32,
    }


def test_count_new_event_ids_ignores_duplicates() -> None:
    seen = {"evt-1"}
    records = [
        {"event": type("Event", (), {"unique_event_id": "evt-1"})()},
        {"event": type("Event", (), {"unique_event_id": "evt-2"})()},
        {"event": type("Event", (), {"unique_event_id": "evt-2"})()},
    ]

    assert count_new_event_ids(seen, records) == 1
    assert seen == {"evt-1", "evt-2"}


def test_delete_local_queues_ignores_missing_localstack(monkeypatch) -> None:
    class BrokenSqs:
        def delete_queue(self, **kwargs):
            raise EndpointConnectionError(endpoint_url="http://localhost:4566")

    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: BrokenSqs())

    _delete_local_queues("http://localhost:4566", "eu-west-1", "queue", "dlq")


@pytest.mark.asyncio
async def test_optimized_pipeline_starts_consumers_before_stream_finishes(monkeypatch) -> None:
    events = []

    async def fake_producer(**kwargs):
        events.append("producer-start")
        await asyncio.sleep(0)
        events.append("producer-finish")

    async def fake_consumer(**kwargs):
        events.append("consumer-start")
        await asyncio.sleep(0)
        events.append("consumer-finish")
        return 3

    monkeypatch.setattr(
        "scripts.perf_streaming_e2e._produce_stream_events", fake_producer, raising=False
    )
    monkeypatch.setattr("scripts.perf_streaming_e2e._consume_optimized", fake_consumer)

    processed = await e2e._run_optimized_streaming_pipeline(
        settings=object(),
        sqs_client=object(),
        database_url="postgresql://test",
        total_messages=3,
        batch_sizes=[3],
        stream_seconds=0,
        realtime=False,
        timings={},
        timeout_seconds=1,
        worker_count=1,
        worker_concurrency=1,
        db_batch_size=1,
        sqs_batch_size=1,
        message_group_partitions=1,
    )

    assert processed == 3
    assert events.index("consumer-start") < events.index("producer-finish")
