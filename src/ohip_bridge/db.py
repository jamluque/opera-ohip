from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from ohip_bridge import metrics
from ohip_bridge.config import Settings
from ohip_bridge.events import stable_json

logger = logging.getLogger(__name__)


class EventRepository:
    def __init__(self, settings: Settings) -> None:
        self.database_url = settings.database_url.get_secret_value()

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            yield conn

    def persist_event(
        self,
        *,
        unique_event_id: str,
        hotel_id: str,
        module: str | None,
        action_type: str | None,
        occurred_at: datetime,
        raw_s3_key: str,
        payload: dict[str, Any],
        offset: str | None,
    ) -> bool:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ohip_events (
                        unique_event_id,
                        hotel_id,
                        module,
                        action_type,
                        occurred_at,
                        raw_s3_key,
                        payload,
                        stream_offset
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (unique_event_id) DO NOTHING
                    """,
                    (
                        unique_event_id,
                        hotel_id,
                        module,
                        action_type,
                        occurred_at,
                        raw_s3_key,
                        stable_json(payload),
                        offset,
                    ),
                )
                inserted = cur.rowcount == 1
            conn.commit()
        metrics.database_writes.inc()
        logger.info(
            "persisted event in PostgreSQL",
            extra={"_event_id": unique_event_id, "_hotel_id": hotel_id, "inserted": inserted},
        )
        return inserted
