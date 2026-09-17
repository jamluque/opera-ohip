from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import shutil
import threading
import time
from contextlib import suppress
from datetime import date
from pathlib import Path
from statistics import mean
from types import SimpleNamespace
from typing import Any

import boto3
import psycopg
from botocore.exceptions import ClientError, EndpointConnectionError
from psycopg.rows import dict_row
from pydantic import SecretStr

from ohip_bridge.analytics_snapshot import AnalyticsSettings, AnalyticsSnapshotJob
from ohip_bridge.enrichment_service import OperaEnrichmentService
from ohip_bridge.event_router import EventRouter
from ohip_bridge.events import parse_ohip_event, stable_json
from ohip_bridge.graphql import OhipStreamingClient
from ohip_bridge.identifier_resolver import IdentifierResolver
from ohip_bridge.ohip_client import OHIPResponse
from ohip_bridge.opera_event_parser import OperaEventParser
from ohip_bridge.sqs import SqsConsumer, SqsPublisher
from ohip_bridge.sqs_message_processor import SQSMessageProcessor
from ohip_bridge.transformers import ReservationTransformer
from scripts.perf_streaming_load import _batches, _event, _graphql_next, _reservation_response

PIPELINE_STAGES = (
    "stream_extract",
    "sqs_publish",
    "sqs_receive",
    "enrich_transform",
    "enrich_persist",
    "db_batch_persist",
    "sqs_delete",
    "analytics_snapshot",
)


class LocalOhipClient:
    async def get_reservation(self, hotel_id: str, reservation_id: str) -> OHIPResponse:
        return OHIPResponse(
            "getReservation",
            "reservation",
            reservation_id,
            _reservation_response(reservation_id),
            200,
        )


def _stats(values: list[float]) -> dict[str, float | int]:
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "total_ms": 0, "avg_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0}

    def percentile(value: float) -> float:
        index = min(len(ordered) - 1, int((len(ordered) - 1) * value))
        return ordered[index]

    return {
        "count": len(ordered),
        "total_ms": round(sum(ordered), 3),
        "avg_ms": round(mean(ordered), 6),
        "p50_ms": round(percentile(0.50), 6),
        "p95_ms": round(percentile(0.95), 6),
        "p99_ms": round(percentile(0.99), 6),
        "max_ms": round(ordered[-1], 6),
    }


def _record(timings: dict[str, list[float]], name: str, started: int, repeat: int = 1) -> None:
    elapsed = (time.perf_counter_ns() - started) / 1_000_000
    timings[name].extend([elapsed / repeat] * repeat)


def message_group_id(prefix: str, partitions: int, hotel_id: str, key: str | None) -> str:
    value = f"{hotel_id}:{key or ''}".encode()
    partition = int(hashlib.sha256(value).hexdigest(), 16) % max(1, partitions)
    return f"{prefix}-{partition:02d}"


def new_report(
    *,
    total_messages: int,
    seed: int | None,
    realtime: bool,
    min_seconds: float = 1,
    max_seconds: float = 5,
    min_batch_size: int = 1,
    max_batch_size: int = 100,
    worker_count: int = 1,
    worker_concurrency: int = 1,
    db_batch_size: int = 1,
    sqs_batch_size: int = 1,
    message_group_partitions: int = 1,
) -> dict[str, Any]:
    rng = random.Random(seed)
    stream_seconds = rng.uniform(min_seconds, max_seconds)
    batch_sizes = _batches(total_messages, min_batch_size, max_batch_size, rng)
    return {
        "input": {
            "total_messages": total_messages,
            "min_seconds": min_seconds,
            "max_seconds": max_seconds,
            "min_batch_size": min_batch_size,
            "max_batch_size": max_batch_size,
            "seed": seed,
            "realtime": realtime,
        },
        "summary": {
            "processed_messages": 0,
            "target_stream_seconds": round(stream_seconds, 3),
            "elapsed_seconds": 0,
            "throughput_messages_per_second": 0,
        },
        "batches": {
            "count": len(batch_sizes),
            "min_size": min(batch_sizes) if batch_sizes else 0,
            "max_size": max(batch_sizes) if batch_sizes else 0,
            "avg_size": round(mean(batch_sizes), 2) if batch_sizes else 0,
        },
        "pipeline": {name: _stats([]) for name in PIPELINE_STAGES},
        "storage": {},
        "infrastructure_usage": {},
        "optimization": {
            "worker_count": worker_count,
            "worker_concurrency": worker_concurrency,
            "db_batch_size": db_batch_size,
            "sqs_batch_size": sqs_batch_size,
            "message_group_partitions": message_group_partitions,
        },
    }


def _settings(database_url: str, queue_url: str, dlq_url: str | None, region: str) -> Any:
    return SimpleNamespace(
        aws_region=region,
        cloudwatch_metrics_enabled=False,
        cloudwatch_metrics_namespace="Opera/OHIP/E2EPerf",
        database_url=SecretStr(database_url),
        enricher_max_attempts=5,
        sqs_enricher_dlq_url=dlq_url,
        sqs_events_queue_url=queue_url,
        sqs_max_messages=10,
        sqs_message_group_id="opera-ohip-stream",
        sqs_visibility_timeout=120,
        sqs_wait_time_seconds=0,
    )


def _configure_local_aws(endpoint_url: str, region: str) -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
    os.environ["AWS_DEFAULT_REGION"] = region
    os.environ["AWS_ENDPOINT_URL"] = endpoint_url


def _create_local_infra(endpoint_url: str, region: str, prefix: str) -> tuple[str, str]:
    sqs = boto3.client("sqs", region_name=region, endpoint_url=endpoint_url)
    s3 = boto3.client("s3", region_name=region, endpoint_url=endpoint_url)
    dlq_name = f"{prefix}-dlq.fifo"
    queue_name = f"{prefix}.fifo"
    dlq_url = sqs.create_queue(
        QueueName=dlq_name,
        Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
    )["QueueUrl"]
    dlq_arn = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])[
        "Attributes"
    ]["QueueArn"]
    queue_url = sqs.create_queue(
        QueueName=queue_name,
        Attributes={
            "FifoQueue": "true",
            "ContentBasedDeduplication": "false",
            "VisibilityTimeout": "120",
            "RedrivePolicy": json.dumps(
                {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "5"}
            ),
        },
    )["QueueUrl"]
    try:
        bucket_args: dict[str, Any] = {"Bucket": f"{prefix}-raw"}
        if region != "us-east-1":
            bucket_args["CreateBucketConfiguration"] = {"LocationConstraint": region}
        s3.create_bucket(**bucket_args)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "BucketAlreadyOwnedByYou":
            raise
    return queue_url, dlq_url


def _delete_local_queues(endpoint_url: str, region: str, queue_url: str, dlq_url: str) -> None:
    sqs = boto3.client("sqs", region_name=region, endpoint_url=endpoint_url)
    for url in (queue_url, dlq_url):
        with suppress(ClientError, EndpointConnectionError):
            sqs.delete_queue(QueueUrl=url)


def _apply_migrations(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for path in sorted(Path("db/migrations").glob("*.sql")):
                cur.execute(path.read_text(encoding="utf-8"))
        conn.commit()


def _reset_database(database_url: str) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                TRUNCATE
                    opera_analytics.pickup_metric,
                    opera_analytics.reservation_last_status_daily,
                    opera_analytics.reservation_daily_snapshot,
                    opera_raw.resource_snapshot,
                    opera_events.event,
                    opera_core.reservation,
                    opera_core.profile,
                    opera_core.folio,
                    opera_core.folio_transaction,
                    ohip_events
                CASCADE
                """
            )
        conn.commit()


def _storage_counts(database_url: str) -> dict[str, int]:
    queries = {
        "events_completed": "SELECT count(*) FROM opera_events.event WHERE status = 'COMPLETED'",
        "raw_snapshots": "SELECT count(*) FROM opera_raw.resource_snapshot",
        "core_reservations": "SELECT count(*) FROM opera_core.reservation",
        "daily_snapshot_rows": "SELECT count(*) FROM opera_analytics.reservation_daily_snapshot",
        "last_status_rows": "SELECT count(*) FROM opera_analytics.reservation_last_status_daily",
    }
    with psycopg.connect(database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        counts = {}
        for name, sql in queries.items():
            cur.execute(sql)
            counts[name] = int(cur.fetchone()["count"])
        return counts


def _database_size_mb(database_url: str) -> float:
    with psycopg.connect(database_url, row_factory=dict_row) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database()) AS bytes")
        return round(int(cur.fetchone()["bytes"]) / 1024 / 1024, 2)


def _chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def count_new_event_ids(seen: set[str], records: list[dict[str, Any]]) -> int:
    count = 0
    for record in records:
        event_id = record["event"].unique_event_id
        if event_id not in seen:
            seen.add(event_id)
            count += 1
    return count


class InfrastructureMonitor:
    def __init__(self, interval_seconds: float = 2.0) -> None:
        self.interval_seconds = interval_seconds
        self.samples: list[dict[str, float]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self) -> InfrastructureMonitor:
        self._thread.start()
        return self

    def __exit__(self, *args: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self.interval_seconds + 1)

    def summary(self) -> dict[str, Any]:
        return {
            "samples": len(self.samples),
            "cpu_percent": _metric_summary([sample["cpu_percent"] for sample in self.samples]),
            "memory_percent": _metric_summary(
                [sample["memory_percent"] for sample in self.samples]
            ),
            "disk_percent": _metric_summary([sample["disk_percent"] for sample in self.samples]),
        }

    def _run(self) -> None:
        previous = _read_cpu()
        while not self._stop.wait(self.interval_seconds):
            current = _read_cpu()
            self.samples.append(
                {
                    "cpu_percent": _cpu_percent(previous, current),
                    "memory_percent": _memory_percent(),
                    "disk_percent": _disk_percent(),
                }
            )
            previous = current


def _metric_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {"avg": 0, "max": 0}
    return {"avg": round(mean(values), 2), "max": round(max(values), 2)}


def _read_cpu() -> tuple[int, int]:
    parts = Path("/proc/stat").read_text(encoding="utf-8").splitlines()[0].split()[1:]
    values = [int(value) for value in parts]
    idle = values[3] + values[4]
    return sum(values), idle


def _cpu_percent(previous: tuple[int, int], current: tuple[int, int]) -> float:
    total_delta = current[0] - previous[0]
    idle_delta = current[1] - previous[1]
    if total_delta <= 0:
        return 0
    return round((1 - idle_delta / total_delta) * 100, 2)


def _memory_percent() -> float:
    values = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        values[key] = int(value.split()[0])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return round((1 - available / total) * 100, 2) if total else 0


def _disk_percent() -> float:
    usage = shutil.disk_usage(Path.cwd())
    return round(usage.used / usage.total * 100, 2)


async def _consume(
    *,
    settings: Any,
    processor: SQSMessageProcessor,
    total_messages: int,
    timings: dict[str, list[float]],
    timeout_seconds: int,
) -> int:
    processed = 0
    deadline = time.monotonic() + timeout_seconds
    while processed < total_messages and time.monotonic() < deadline:
        started = time.perf_counter_ns()
        messages = processor.sqs.receive()
        if messages:
            _record(timings, "sqs_receive", started, len(messages))
        for message in messages:
            started = time.perf_counter_ns()
            if await processor.process_message(message):
                processed += 1
            _record(timings, "enrich_persist", started)
        if not messages:
            await asyncio.sleep(settings.sqs_wait_time_seconds or 0.01)
    if processed != total_messages:
        raise RuntimeError(f"Processed {processed}/{total_messages} messages before timeout")
    return processed


def _event_body(event: Any) -> str:
    return stable_json(
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


def _publish_event_batch(
    *,
    client: Any,
    queue_url: str,
    events: list[Any],
    group_prefix: str,
    partitions: int,
    timings: dict[str, list[float]],
) -> None:
    for chunk in _chunked(events, 10):
        started = time.perf_counter_ns()
        response = client.send_message_batch(
            QueueUrl=queue_url,
            Entries=[
                {
                    "Id": f"m{index}",
                    "MessageBody": _event_body(event),
                    "MessageGroupId": message_group_id(
                        group_prefix,
                        partitions,
                        event.hotel_id,
                        event.payload.get("primaryKey") or event.unique_event_id,
                    ),
                    "MessageDeduplicationId": event.unique_event_id,
                    "MessageAttributes": {
                        "hotel_id": {"DataType": "String", "StringValue": event.hotel_id},
                        "unique_event_id": {
                            "DataType": "String",
                            "StringValue": event.unique_event_id,
                        },
                    },
                }
                for index, event in enumerate(chunk)
            ],
        )
        if response.get("Failed"):
            raise RuntimeError(f"SQS batch publish failed: {response['Failed']}")
        _record(timings, "sqs_publish", started, len(chunk))


async def _produce_stream_events(
    *,
    sqs_client: Any,
    settings: Any,
    batch_sizes: list[int],
    stream_seconds: float,
    realtime: bool,
    timings: dict[str, list[float]],
    sqs_batch_size: int,
    message_group_partitions: int,
) -> None:
    sleep_per_batch = stream_seconds / max(1, len(batch_sizes))
    next_message = 1
    pending_events: list[Any] = []
    for batch_size in batch_sizes:
        batch_start = time.perf_counter()
        for index in range(next_message, next_message + batch_size):
            graphql_payload = _graphql_next(_event(index))["payload"]
            started = time.perf_counter_ns()
            payload = OhipStreamingClient._extract_payloads(graphql_payload)[0]
            _record(timings, "stream_extract", started)
            pending_events.append(parse_ohip_event(payload))
            if len(pending_events) >= sqs_batch_size:
                await asyncio.to_thread(
                    _publish_event_batch,
                    client=sqs_client,
                    queue_url=settings.sqs_events_queue_url,
                    events=pending_events,
                    group_prefix=settings.sqs_message_group_id,
                    partitions=message_group_partitions,
                    timings=timings,
                )
                pending_events.clear()
        next_message += batch_size
        if realtime:
            remaining_sleep = sleep_per_batch - (time.perf_counter() - batch_start)
            if remaining_sleep > 0:
                await asyncio.sleep(remaining_sleep)
    if pending_events:
        await asyncio.to_thread(
            _publish_event_batch,
            client=sqs_client,
            queue_url=settings.sqs_events_queue_url,
            events=pending_events,
            group_prefix=settings.sqs_message_group_id,
            partitions=message_group_partitions,
            timings=timings,
        )


async def _run_optimized_streaming_pipeline(
    *,
    settings: Any,
    sqs_client: Any,
    database_url: str,
    total_messages: int,
    batch_sizes: list[int],
    stream_seconds: float,
    realtime: bool,
    timings: dict[str, list[float]],
    timeout_seconds: int,
    worker_count: int,
    worker_concurrency: int,
    db_batch_size: int,
    sqs_batch_size: int,
    message_group_partitions: int,
) -> int:
    consumer_task = asyncio.create_task(
        _consume_optimized(
            settings=settings,
            database_url=database_url,
            total_messages=total_messages,
            timings=timings,
            timeout_seconds=timeout_seconds,
            worker_count=worker_count,
            worker_concurrency=worker_concurrency,
            db_batch_size=db_batch_size,
        )
    )
    try:
        await _produce_stream_events(
            sqs_client=sqs_client,
            settings=settings,
            batch_sizes=batch_sizes,
            stream_seconds=stream_seconds,
            realtime=realtime,
            timings=timings,
            sqs_batch_size=sqs_batch_size,
            message_group_partitions=message_group_partitions,
        )
        return await consumer_task
    except Exception:
        consumer_task.cancel()
        with suppress(asyncio.CancelledError):
            await consumer_task
        raise


def _record_from_message(
    *,
    message: dict[str, Any],
    parser: OperaEventParser,
    router: EventRouter,
    resolver: IdentifierResolver,
    transformer: ReservationTransformer,
) -> dict[str, Any]:
    event = parser.parse(SqsConsumer.parse_message(message))
    route = router.route_for(event)
    if route is None:
        raise RuntimeError(f"No route for event {event.unique_event_id}")
    resolved = resolver.resolve(event, route)
    payload = _reservation_response(resolved.value)
    row = transformer.transform(payload, hotel_id=event.hotel_id, reservation_id=resolved.value)
    return {
        "receipt_handle": message["ReceiptHandle"],
        "event": event,
        "resource_id": resolved.value,
        "payload": payload,
        "row": row,
    }


def _persist_reservation_batch(database_url: str, records: list[dict[str, Any]]) -> None:
    event_sql = """
        INSERT INTO opera_events.event (
            unique_event_id, chain_code, hotel_id, stream_offset, primary_key,
            module_name, event_name, occurred_at, completed_at, payload, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s::jsonb, 'COMPLETED')
        ON CONFLICT DO NOTHING
    """
    raw_sql = """
        INSERT INTO opera_raw.resource_snapshot (
            unique_event_id, hotel_id, resource_type, resource_id, operation_id, payload
        )
        VALUES (%s, %s, 'reservation', %s, 'getReservation', %s::jsonb)
        ON CONFLICT (unique_event_id, resource_type, resource_id) DO UPDATE SET
            operation_id = EXCLUDED.operation_id,
            payload = EXCLUDED.payload,
            fetched_at = now()
    """
    reservation_sql = """
        INSERT INTO opera_core.reservation (
            hotel_id, reservation_id, confirmation_no, arrival_date, departure_date,
            reservation_status, source_updated_at, last_event_id, last_event_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (hotel_id, reservation_id) DO UPDATE SET
            confirmation_no = EXCLUDED.confirmation_no,
            arrival_date = EXCLUDED.arrival_date,
            departure_date = EXCLUDED.departure_date,
            reservation_status = EXCLUDED.reservation_status,
            source_updated_at = EXCLUDED.source_updated_at,
            last_event_id = EXCLUDED.last_event_id,
            last_event_at = EXCLUDED.last_event_at,
            updated_at = now()
        WHERE opera_core.reservation.last_event_at IS NULL
           OR opera_core.reservation.last_event_at <= EXCLUDED.last_event_at
    """
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.executemany(
            event_sql,
            [
                (
                    record["event"].unique_event_id,
                    record["event"].chain_code,
                    record["event"].hotel_id,
                    record["event"].offset,
                    record["event"].primary_key,
                    record["event"].module_name,
                    record["event"].event_name,
                    record["event"].occurred_at,
                    stable_json(record["event"].payload),
                )
                for record in records
            ],
        )
        cur.executemany(
            raw_sql,
            [
                (
                    record["event"].unique_event_id,
                    record["event"].hotel_id,
                    record["resource_id"],
                    stable_json(record["payload"]),
                )
                for record in records
            ],
        )
        cur.executemany(
            reservation_sql,
            [
                (
                    record["row"]["hotel_id"],
                    record["row"]["reservation_id"],
                    record["row"].get("confirmation_no"),
                    record["row"].get("arrival_date"),
                    record["row"].get("departure_date"),
                    record["row"].get("reservation_status"),
                    record["row"].get("source_updated_at"),
                    record["event"].unique_event_id,
                    record["event"].occurred_at,
                )
                for record in records
            ],
        )
        conn.commit()


def _delete_message_batch(
    *,
    client: Any,
    queue_url: str,
    receipt_handles: list[str],
    timings: dict[str, list[float]],
) -> None:
    for chunk in _chunked(receipt_handles, 10):
        started = time.perf_counter_ns()
        response = client.delete_message_batch(
            QueueUrl=queue_url,
            Entries=[
                {"Id": f"m{index}", "ReceiptHandle": receipt_handle}
                for index, receipt_handle in enumerate(chunk)
            ],
        )
        if response.get("Failed"):
            raise RuntimeError(f"SQS batch delete failed: {response['Failed']}")
        _record(timings, "sqs_delete", started, len(chunk))


async def _flush_records(
    *,
    records: list[dict[str, Any]],
    database_url: str,
    sqs_client: Any,
    queue_url: str,
    timings: dict[str, list[float]],
) -> int:
    if not records:
        return 0
    started = time.perf_counter_ns()
    await asyncio.to_thread(_persist_reservation_batch, database_url, records)
    _record(timings, "db_batch_persist", started, len(records))
    await asyncio.to_thread(
        _delete_message_batch,
        client=sqs_client,
        queue_url=queue_url,
        receipt_handles=[record["receipt_handle"] for record in records],
        timings=timings,
    )
    return len(records)


async def _optimized_consumer_task(
    *,
    settings: Any,
    database_url: str,
    timings: dict[str, list[float]],
    processed: dict[str, int],
    seen_event_ids: set[str],
    lock: asyncio.Lock,
    total_messages: int,
    db_batch_size: int,
    deadline: float,
) -> None:
    sqs_client = boto3.client("sqs", region_name=settings.aws_region)
    parser = OperaEventParser()
    router = EventRouter.from_yaml("config/event-router.yaml")
    resolver = IdentifierResolver()
    transformer = ReservationTransformer()
    consumer = SqsConsumer(settings)
    records: list[dict[str, Any]] = []
    last_flush = time.monotonic()

    while time.monotonic() < deadline:
        async with lock:
            if processed["count"] >= total_messages:
                break
        started = time.perf_counter_ns()
        messages = await asyncio.to_thread(consumer.receive)
        if messages:
            _record(timings, "sqs_receive", started, len(messages))
        for message in messages:
            started = time.perf_counter_ns()
            records.append(
                _record_from_message(
                    message=message,
                    parser=parser,
                    router=router,
                    resolver=resolver,
                    transformer=transformer,
                )
            )
            _record(timings, "enrich_transform", started)

        flush_due = len(records) >= db_batch_size or (
            records and time.monotonic() - last_flush >= 1
        )
        if flush_due:
            done = await _flush_records(
                records=records,
                database_url=database_url,
                sqs_client=sqs_client,
                queue_url=settings.sqs_events_queue_url,
                timings=timings,
            )
            async with lock:
                processed["count"] += min(done, count_new_event_ids(seen_event_ids, records))
            records.clear()
            last_flush = time.monotonic()
        if not messages:
            await asyncio.sleep(0.01)

    done = await _flush_records(
        records=records,
        database_url=database_url,
        sqs_client=sqs_client,
        queue_url=settings.sqs_events_queue_url,
        timings=timings,
    )
    async with lock:
        processed["count"] += min(done, count_new_event_ids(seen_event_ids, records))
    records.clear()


async def _consume_optimized(
    *,
    settings: Any,
    database_url: str,
    total_messages: int,
    timings: dict[str, list[float]],
    timeout_seconds: int,
    worker_count: int,
    worker_concurrency: int,
    db_batch_size: int,
) -> int:
    processed = {"count": 0}
    seen_event_ids: set[str] = set()
    lock = asyncio.Lock()
    deadline = time.monotonic() + timeout_seconds
    tasks = [
        asyncio.create_task(
            _optimized_consumer_task(
                settings=settings,
                database_url=database_url,
                timings=timings,
                processed=processed,
                seen_event_ids=seen_event_ids,
                lock=lock,
                total_messages=total_messages,
                db_batch_size=db_batch_size,
                deadline=deadline,
            )
        )
        for _ in range(worker_count * worker_concurrency)
    ]
    await asyncio.gather(*tasks)
    if processed["count"] != total_messages:
        raise RuntimeError(f"Processed {processed['count']}/{total_messages} messages")
    return processed["count"]


async def _run_e2e_async(
    *,
    total_messages: int,
    min_seconds: float,
    max_seconds: float,
    min_batch_size: int,
    max_batch_size: int,
    seed: int | None,
    realtime: bool,
    endpoint_url: str,
    region: str,
    database_url: str,
    snapshot_date: date,
    timeout_seconds: int,
    optimized: bool,
    worker_count: int,
    worker_concurrency: int,
    db_batch_size: int,
    sqs_batch_size: int,
    message_group_partitions: int,
) -> dict[str, Any]:
    _configure_local_aws(endpoint_url, region)
    prefix = f"opera-ohip-e2e-{int(time.time())}"
    queue_url, dlq_url = _create_local_infra(endpoint_url, region, prefix)
    settings = _settings(database_url, queue_url, dlq_url, region)
    report = new_report(
        total_messages=total_messages,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
        min_batch_size=min_batch_size,
        max_batch_size=max_batch_size,
        seed=seed,
        realtime=realtime,
        worker_count=worker_count,
        worker_concurrency=worker_concurrency,
        db_batch_size=db_batch_size,
        sqs_batch_size=sqs_batch_size,
        message_group_partitions=message_group_partitions,
    )
    timings: dict[str, list[float]] = {name: [] for name in PIPELINE_STAGES}
    rng = random.Random(seed)
    stream_seconds = rng.uniform(min_seconds, max_seconds)
    batch_sizes = _batches(total_messages, min_batch_size, max_batch_size, rng)
    sleep_per_batch = stream_seconds / max(1, len(batch_sizes))
    started_at = time.perf_counter()

    try:
        _apply_migrations(database_url)
        _reset_database(database_url)
        with InfrastructureMonitor() as monitor:
            sqs_client = boto3.client("sqs", region_name=region)
            if optimized:
                processed = await _run_optimized_streaming_pipeline(
                    settings=settings,
                    sqs_client=sqs_client,
                    database_url=database_url,
                    total_messages=total_messages,
                    batch_sizes=batch_sizes,
                    stream_seconds=stream_seconds,
                    realtime=realtime,
                    timings=timings,
                    timeout_seconds=timeout_seconds,
                    worker_count=worker_count,
                    worker_concurrency=worker_concurrency,
                    db_batch_size=db_batch_size,
                    sqs_batch_size=sqs_batch_size,
                    message_group_partitions=message_group_partitions,
                )
            else:
                publisher = SqsPublisher(settings)
                next_message = 1
                for batch_size in batch_sizes:
                    batch_start = time.perf_counter()
                    for index in range(next_message, next_message + batch_size):
                        graphql_payload = _graphql_next(_event(index))["payload"]
                        started = time.perf_counter_ns()
                        payload = OhipStreamingClient._extract_payloads(graphql_payload)[0]
                        _record(timings, "stream_extract", started)

                        event = parse_ohip_event(payload)
                        started = time.perf_counter_ns()
                        publisher.publish(event)
                        _record(timings, "sqs_publish", started)
                    next_message += batch_size
                    if realtime:
                        remaining_sleep = sleep_per_batch - (time.perf_counter() - batch_start)
                        if remaining_sleep > 0:
                            time.sleep(remaining_sleep)
                service = OperaEnrichmentService(
                    settings=settings,
                    router=EventRouter.from_yaml("config/event-router.yaml"),
                    resolver=IdentifierResolver(),
                    ohip_client=LocalOhipClient(),  # type: ignore[arg-type]
                )
                processor = SQSMessageProcessor(
                    settings, SqsConsumer(settings), OperaEventParser(), service
                )
                processed = await _consume(
                    settings=settings,
                    processor=processor,
                    total_messages=total_messages,
                    timings=timings,
                    timeout_seconds=timeout_seconds,
                )

            started = time.perf_counter_ns()
            AnalyticsSnapshotJob(
                AnalyticsSettings(
                    database_url=SecretStr(database_url),
                    analytics_snapshot_date=snapshot_date,
                    analytics_pickup_days=[1],
                )
            ).run()
            _record(timings, "analytics_snapshot", started)

            elapsed = time.perf_counter() - started_at
            report["summary"] = {
                "processed_messages": processed,
                "target_stream_seconds": round(stream_seconds, 3),
                "elapsed_seconds": round(elapsed, 3),
                "throughput_messages_per_second": round(processed / elapsed, 2)
                if elapsed
                else 0,
            }
            report["pipeline"] = {name: _stats(values) for name, values in timings.items()}
            report["storage"] = _storage_counts(database_url)
            report["storage"]["database_size_mb"] = _database_size_mb(database_url)
            report["infrastructure_usage"] = monitor.summary()
            return report
    finally:
        _delete_local_queues(endpoint_url, region, queue_url, dlq_url)


def run_e2e_load_test(
    *,
    total_messages: int = 10_000,
    min_seconds: float = 1,
    max_seconds: float = 5,
    min_batch_size: int = 1,
    max_batch_size: int = 100,
    seed: int | None = None,
    realtime: bool = True,
    endpoint_url: str = "http://localhost:4566",
    region: str = "eu-west-1",
    database_url: str = "postgresql://app_user:app_password@localhost:5432/opera_ohip",
    snapshot_date: date | None = None,
    timeout_seconds: int = 120,
    optimized: bool = False,
    worker_count: int = 8,
    worker_concurrency: int = 4,
    db_batch_size: int = 100,
    sqs_batch_size: int = 10,
    message_group_partitions: int = 32,
) -> dict[str, Any]:
    return asyncio.run(
        _run_e2e_async(
            total_messages=total_messages,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            min_batch_size=min_batch_size,
            max_batch_size=max_batch_size,
            seed=seed,
            realtime=realtime,
            endpoint_url=endpoint_url,
            region=region,
            database_url=database_url,
            snapshot_date=snapshot_date or date.today(),
            timeout_seconds=timeout_seconds,
            optimized=optimized,
            worker_count=worker_count,
            worker_concurrency=worker_concurrency,
            db_batch_size=db_batch_size,
            sqs_batch_size=min(sqs_batch_size, 10),
            message_group_partitions=message_group_partitions,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--messages", type=int, default=10_000)
    parser.add_argument("--min-seconds", type=float, default=1)
    parser.add_argument("--max-seconds", type=float, default=5)
    parser.add_argument("--min-batch-size", type=int, default=1)
    parser.add_argument("--max-batch-size", type=int, default=100)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--no-realtime", action="store_true")
    parser.add_argument("--optimized", action="store_true")
    parser.add_argument("--worker-count", type=int, default=8)
    parser.add_argument("--worker-concurrency", type=int, default=4)
    parser.add_argument("--db-batch-size", type=int, default=100)
    parser.add_argument("--sqs-batch-size", type=int, default=10)
    parser.add_argument("--message-group-partitions", type=int, default=32)
    parser.add_argument("--endpoint-url", default=os.getenv("ENDPOINT_URL", "http://localhost:4566"))
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "eu-west-1"))
    parser.add_argument(
        "--database-url",
        default=os.getenv(
            "DATABASE_URL", "postgresql://app_user:app_password@localhost:5432/opera_ohip"
        ),
    )
    parser.add_argument("--snapshot-date", type=date.fromisoformat)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = run_e2e_load_test(
        total_messages=args.messages,
        min_seconds=args.min_seconds,
        max_seconds=args.max_seconds,
        min_batch_size=args.min_batch_size,
        max_batch_size=args.max_batch_size,
        seed=args.seed,
        realtime=not args.no_realtime,
        endpoint_url=args.endpoint_url,
        region=args.region,
        database_url=args.database_url,
        snapshot_date=args.snapshot_date,
        timeout_seconds=args.timeout_seconds,
        optimized=args.optimized,
        worker_count=args.worker_count,
        worker_concurrency=args.worker_concurrency,
        db_batch_size=args.db_batch_size,
        sqs_batch_size=args.sqs_batch_size,
        message_group_partitions=args.message_group_partitions,
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(f"{output}\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
