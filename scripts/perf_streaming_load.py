from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from statistics import mean
from typing import Any

from ohip_bridge.event_router import EventRouter
from ohip_bridge.graphql import OhipStreamingClient
from ohip_bridge.identifier_resolver import IdentifierResolver
from ohip_bridge.opera_event_parser import OperaEventParser
from ohip_bridge.transformers import ReservationTransformer


def _event(index: int) -> dict[str, Any]:
    reservation_id = f"resv-perf-{index:05d}"
    return {
        "metadata": {"offset": str(index), "uniqueEventId": f"evt-perf-{index:05d}"},
        "chainCode": "CHAIN",
        "hotelId": "MAD01",
        "moduleName": "Reservation",
        "eventName": "UpdateReservation",
        "primaryKey": reservation_id,
        "timestamp": "2026-08-18T12:00:00Z",
        "detail": [{"elementName": "reservationId", "newValue": reservation_id}],
    }


def _graphql_next(event: dict[str, Any]) -> dict[str, Any]:
    return {"type": "next", "payload": {"data": {"newEvent": event}}}


def _reservation_response(reservation_id: str) -> dict[str, Any]:
    return {
        "reservation": {
            "reservationId": reservation_id,
            "confirmationNo": f"CNF-{reservation_id[-5:]}",
            "arrivalDate": "2026-09-02",
            "departureDate": "2026-09-05",
            "reservationStatus": "RESERVED",
            "lastModifyDateTime": "2026-08-18T12:00:01Z",
        }
    }


def _batches(total: int, min_size: int, max_size: int, rng: random.Random) -> list[int]:
    batches = []
    remaining = total
    while remaining:
        size = min(remaining, rng.randint(min_size, max_size))
        batches.append(size)
        remaining -= size
    return batches


def _record(timings: dict[str, list[float]], name: str, started: int) -> None:
    timings[name].append((time.perf_counter_ns() - started) / 1_000_000)


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


def run_load_test(
    *,
    total_messages: int = 10_000,
    min_seconds: int = 1,
    max_seconds: int = 5,
    min_batch_size: int = 1,
    max_batch_size: int = 100,
    seed: int | None = None,
    realtime: bool = True,
) -> dict[str, Any]:
    rng = random.Random(seed)
    stream_seconds = rng.uniform(min_seconds, max_seconds)
    batch_sizes = _batches(total_messages, min_batch_size, max_batch_size, rng)
    parser = OperaEventParser()
    router = EventRouter.from_yaml("config/event-router.yaml")
    resolver = IdentifierResolver()
    transformer = ReservationTransformer()
    timings: dict[str, list[float]] = {
        "stream_extract": [],
        "parse_event": [],
        "route_event": [],
        "resolve_identifier": [],
        "fetch_ohip_rest": [],
        "transform_core": [],
    }
    rows = 0
    next_message = 1
    started_at = time.perf_counter()
    sleep_per_batch = stream_seconds / max(1, len(batch_sizes))

    for batch_size in batch_sizes:
        batch_start = time.perf_counter()
        for index in range(next_message, next_message + batch_size):
            graphql_payload = _graphql_next(_event(index))["payload"]
            started = time.perf_counter_ns()
            payload = OhipStreamingClient._extract_payloads(graphql_payload)[0]
            _record(timings, "stream_extract", started)

            started = time.perf_counter_ns()
            event = parser.parse(payload)
            _record(timings, "parse_event", started)

            started = time.perf_counter_ns()
            route = router.route_for(event)
            _record(timings, "route_event", started)
            if route is None:
                raise RuntimeError(f"No route for event {event.unique_event_id}")

            started = time.perf_counter_ns()
            resolved = resolver.resolve(event, route)
            _record(timings, "resolve_identifier", started)

            started = time.perf_counter_ns()
            response = _reservation_response(resolved.value)
            _record(timings, "fetch_ohip_rest", started)

            started = time.perf_counter_ns()
            transformer.transform(response, hotel_id=event.hotel_id, reservation_id=resolved.value)
            _record(timings, "transform_core", started)
            rows += 1

        next_message += batch_size
        if realtime:
            remaining_sleep = sleep_per_batch - (time.perf_counter() - batch_start)
            if remaining_sleep > 0:
                time.sleep(remaining_sleep)

    elapsed = time.perf_counter() - started_at
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
            "processed_messages": rows,
            "generated_batches": len(batch_sizes),
            "target_stream_seconds": round(stream_seconds, 3),
            "elapsed_seconds": round(elapsed, 3),
            "throughput_messages_per_second": round(rows / elapsed, 2) if elapsed else 0,
        },
        "batches": {
            "count": len(batch_sizes),
            "min_size": min(batch_sizes) if batch_sizes else 0,
            "max_size": max(batch_sizes) if batch_sizes else 0,
            "avg_size": round(mean(batch_sizes), 2) if batch_sizes else 0,
        },
        "pipeline": {name: _stats(values) for name, values in timings.items()},
    }


def main() -> None:
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("--messages", type=int, default=10_000)
    arg_parser.add_argument("--min-seconds", type=int, default=1)
    arg_parser.add_argument("--max-seconds", type=int, default=5)
    arg_parser.add_argument("--min-batch-size", type=int, default=1)
    arg_parser.add_argument("--max-batch-size", type=int, default=100)
    arg_parser.add_argument("--seed", type=int)
    arg_parser.add_argument("--no-realtime", action="store_true")
    arg_parser.add_argument("--output")
    args = arg_parser.parse_args()

    report = run_load_test(
        total_messages=args.messages,
        min_seconds=args.min_seconds,
        max_seconds=args.max_seconds,
        min_batch_size=args.min_batch_size,
        max_batch_size=args.max_batch_size,
        seed=args.seed,
        realtime=not args.no_realtime,
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(f"{output}\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
