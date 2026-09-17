from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ohip_bridge.events import stable_json
from ohip_bridge.logging import configure_logging

logger = logging.getLogger(__name__)


class AnalyticsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"
    log_level: str = "INFO"
    database_url: SecretStr
    analytics_snapshot_date: date | None = None
    analytics_pickup_days: list[int] = [1, 3, 7, 15]
    analytics_stay_horizon_days: int = 730


    @field_validator("analytics_snapshot_date", mode="before")
    @classmethod
    def _empty_snapshot_date(cls, value: str | date | None) -> date | None:
        if value == "":
            return None
        return value

    @field_validator("analytics_pickup_days", mode="before")
    @classmethod
    def _split_pickup_days(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, list):
            return [int(item) for item in value]
        return [int(item.strip()) for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class ReservationSnapshotRow:
    snapshot_date: date
    hotel_id: str
    stay_date: date
    reservation_id: str
    confirmation_no: str | None
    room_type: str | None
    rate_code: str | None
    market_code: str | None
    source_code: str | None
    channel_code: str | None
    reservation_status: str | None
    rooms: Decimal
    room_revenue: Decimal
    total_revenue: Decimal
    adr: Decimal | None
    created_date: date | None
    cancelled_date: date | None
    source_updated_at: datetime | None
    last_event_id: str | None
    last_event_at: datetime | None
    payload: dict[str, Any] | None


class ReservationSnapshotTransformer:
    def transform(self, row: dict[str, Any], snapshot_date: date) -> list[ReservationSnapshotRow]:
        payload = row.get("raw_payload") or {}
        arrival = self._date(row.get("arrival_date") or self._find(payload, "arrivalDate"))
        departure = self._date(row.get("departure_date") or self._find(payload, "departureDate"))
        if arrival is None or departure is None or departure <= arrival:
            return []
        rows: list[ReservationSnapshotRow] = []
        stay_date = arrival
        while stay_date < departure:
            if stay_date >= snapshot_date:
                rows.append(self._snapshot_row(row, payload, snapshot_date, stay_date))
            stay_date += timedelta(days=1)
        return rows

    def _snapshot_row(
        self, row: dict[str, Any], payload: dict[str, Any], snapshot_date: date, stay_date: date
    ) -> ReservationSnapshotRow:
        rooms = self._decimal(
            self._find(payload, "rooms") or self._find(payload, "numberOfRooms") or 1
        )
        room_revenue = self._decimal(
            self._find_for_date(payload, stay_date, "roomRevenue")
            or self._find(payload, "roomRevenue")
            or self._find(payload, "rateAmount")
            or 0
        )
        total_revenue = self._decimal(self._find(payload, "totalRevenue") or room_revenue)
        adr = room_revenue / rooms if rooms else None
        return ReservationSnapshotRow(
            snapshot_date=snapshot_date,
            hotel_id=str(row["hotel_id"]),
            stay_date=stay_date,
            reservation_id=str(row["reservation_id"]),
            confirmation_no=row.get("confirmation_no")
            or self._text(self._find(payload, "confirmationNo")),
            room_type=self._text(self._find(payload, "roomType")),
            rate_code=self._text(self._find(payload, "rateCode")),
            market_code=self._text(self._find(payload, "marketCode")),
            source_code=self._text(self._find(payload, "sourceCode")),
            channel_code=self._text(self._find(payload, "channelCode")),
            reservation_status=row.get("reservation_status")
            or self._text(self._find(payload, "reservationStatus")),
            rooms=rooms,
            room_revenue=room_revenue,
            total_revenue=total_revenue,
            adr=adr,
            created_date=self._date(
                self._find(payload, "createdDate") or self._find(payload, "createDate")
            ),
            cancelled_date=self._date(self._find(payload, "cancelledDate")),
            source_updated_at=row.get("source_updated_at"),
            last_event_id=row.get("last_event_id"),
            last_event_at=row.get("last_event_at"),
            payload=payload,
        )

    def _find_for_date(self, payload: Any, stay_date: date, name: str) -> Any:
        if isinstance(payload, dict):
            for key in ("dailyRates", "roomRates", "rateDetails", "stayDetails"):
                values = payload.get(key)
                if isinstance(values, list):
                    for item in values:
                        if not isinstance(item, dict):
                            continue
                        item_date = self._date(
                            item.get("stayDate") or item.get("businessDate") or item.get("date")
                        )
                        if item_date == stay_date and item.get(name) is not None:
                            return item.get(name)
            for value in payload.values():
                found = self._find_for_date(value, stay_date, name)
                if found is not None:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = self._find_for_date(item, stay_date, name)
                if found is not None:
                    return found
        return None

    def _find(self, payload: Any, name: str) -> Any:
        if isinstance(payload, dict):
            if name in payload and payload[name] not in (None, ""):
                return payload[name]
            for value in payload.values():
                found = self._find(value, name)
                if found not in (None, ""):
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = self._find(item, name)
                if found not in (None, ""):
                    return found
        return None

    def _date(self, value: Any) -> date | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None

    def _decimal(self, value: Any) -> Decimal:
        if value in (None, ""):
            return Decimal("0")
        return Decimal(str(value))

    def _text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)


class AnalyticsSnapshotJob:
    def __init__(self, settings: AnalyticsSettings) -> None:
        self.settings = settings
        self.transformer = ReservationSnapshotTransformer()

    def run(self) -> None:
        snapshot_date = self.settings.analytics_snapshot_date or datetime.now(UTC).date()
        with psycopg.connect(
            self.settings.database_url.get_secret_value(), row_factory=dict_row
        ) as conn:
            try:
                self._build_daily_snapshot(conn, snapshot_date)
                self._refresh_last_status(conn, snapshot_date)
                self._refresh_pickups(conn, snapshot_date)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def _build_daily_snapshot(self, conn: psycopg.Connection[Any], snapshot_date: date) -> None:
        rows_written = 0
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM opera_analytics.reservation_daily_snapshot WHERE snapshot_date = %s",
                (snapshot_date,),
            )
            cur.execute(
                """
                SELECT
                    r.*,
                    raw.payload AS raw_payload
                FROM opera_core.reservation r
                LEFT JOIN LATERAL (
                    SELECT payload
                    FROM opera_raw.resource_snapshot s
                    WHERE s.resource_type = 'reservation'
                      AND s.hotel_id = r.hotel_id
                      AND s.resource_id = r.reservation_id
                    ORDER BY s.fetched_at DESC
                    LIMIT 1
                ) raw ON true
                WHERE r.departure_date >= %s
                  AND r.arrival_date <= %s + (%s || ' days')::interval
                """,
                (snapshot_date, snapshot_date, self.settings.analytics_stay_horizon_days),
            )
            for source_row in cur.fetchall():
                for snapshot_row in self.transformer.transform(dict(source_row), snapshot_date):
                    self._insert_snapshot_row(cur, snapshot_row)
                    rows_written += 1
        logger.info("analytics daily snapshot built", extra={"rows_written": rows_written})

    def _refresh_last_status(self, conn: psycopg.Connection[Any], snapshot_date: date) -> None:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL work_mem = '256MB'")
            cur.execute(
                """
                DELETE FROM opera_analytics.reservation_last_status_daily
                 WHERE snapshot_date = %s
                """,
                (snapshot_date,),
            )
            cur.execute(
                """
                INSERT INTO opera_analytics.reservation_last_status_daily (
                    snapshot_date,
                    hotel_id,
                    reservation_id,
                    confirmation_no,
                    arrival_date,
                    departure_date,
                    last_status,
                    last_status_event_at,
                    last_event_id,
                    room_type,
                    rate_code,
                    market_code,
                    source_code,
                    channel_code,
                    source_updated_at,
                    payload
                )
                SELECT
                    status.snapshot_date,
                    status.hotel_id,
                    status.reservation_id,
                    status.confirmation_no,
                    status.arrival_date,
                    status.departure_date,
                    status.reservation_status,
                    status.last_status_event_at,
                    status.last_event_id,
                    status.room_type,
                    status.rate_code,
                    status.market_code,
                    status.source_code,
                    status.channel_code,
                    status.source_updated_at,
                    status.payload
                FROM (
                    SELECT
                        snapshot_date,
                        hotel_id,
                        reservation_id,
                        confirmation_no,
                        reservation_status,
                        last_event_id,
                        room_type,
                        rate_code,
                        market_code,
                        source_code,
                        channel_code,
                        payload,
                        MIN(stay_date) OVER reservation_window AS arrival_date,
                        (MAX(stay_date) OVER reservation_window + INTERVAL '1 day')::date
                            AS departure_date,
                        MAX(last_event_at) OVER reservation_window AS last_status_event_at,
                        MAX(source_updated_at) OVER reservation_window AS source_updated_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY snapshot_date, hotel_id, reservation_id
                            ORDER BY last_event_at DESC NULLS LAST, stay_date ASC
                        ) AS row_number
                    FROM opera_analytics.reservation_daily_snapshot
                    WHERE snapshot_date = %s
                    WINDOW reservation_window AS (
                        PARTITION BY snapshot_date, hotel_id, reservation_id
                    )
                ) status
                WHERE status.row_number = 1
                ON CONFLICT (snapshot_date, hotel_id, reservation_id) DO UPDATE SET
                    snapshot_taken_at = now(),
                    confirmation_no = EXCLUDED.confirmation_no,
                    arrival_date = EXCLUDED.arrival_date,
                    departure_date = EXCLUDED.departure_date,
                    last_status = EXCLUDED.last_status,
                    last_status_event_at = EXCLUDED.last_status_event_at,
                    last_event_id = EXCLUDED.last_event_id,
                    room_type = EXCLUDED.room_type,
                    rate_code = EXCLUDED.rate_code,
                    market_code = EXCLUDED.market_code,
                    source_code = EXCLUDED.source_code,
                    channel_code = EXCLUDED.channel_code,
                    source_updated_at = EXCLUDED.source_updated_at,
                    payload = EXCLUDED.payload
                """,
                (snapshot_date,),
            )
        logger.info("analytics last status refreshed", extra={"snapshot_date": snapshot_date})

    def _insert_snapshot_row(self, cur: Any, row: ReservationSnapshotRow) -> None:
        cur.execute(
            """
            INSERT INTO opera_analytics.reservation_daily_snapshot (
                snapshot_date, hotel_id, stay_date, reservation_id, confirmation_no,
                room_type, rate_code, market_code, source_code, channel_code,
                reservation_status, rooms, room_revenue, total_revenue, adr,
                created_date, cancelled_date, source_updated_at, last_event_id,
                last_event_at, payload
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (snapshot_date, hotel_id, stay_date, reservation_id) DO UPDATE SET
                confirmation_no = EXCLUDED.confirmation_no,
                room_type = EXCLUDED.room_type,
                rate_code = EXCLUDED.rate_code,
                market_code = EXCLUDED.market_code,
                source_code = EXCLUDED.source_code,
                channel_code = EXCLUDED.channel_code,
                reservation_status = EXCLUDED.reservation_status,
                rooms = EXCLUDED.rooms,
                room_revenue = EXCLUDED.room_revenue,
                total_revenue = EXCLUDED.total_revenue,
                adr = EXCLUDED.adr,
                payload = EXCLUDED.payload
            """,
            (
                row.snapshot_date,
                row.hotel_id,
                row.stay_date,
                row.reservation_id,
                row.confirmation_no,
                row.room_type,
                row.rate_code,
                row.market_code,
                row.source_code,
                row.channel_code,
                row.reservation_status,
                row.rooms,
                row.room_revenue,
                row.total_revenue,
                row.adr,
                row.created_date,
                row.cancelled_date,
                row.source_updated_at,
                row.last_event_id,
                row.last_event_at,
                stable_json(row.payload or {}),
            ),
        )

    def _refresh_pickups(self, conn: psycopg.Connection[Any], snapshot_date: date) -> None:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM opera_analytics.pickup_metric WHERE snapshot_date = %s",
                (snapshot_date,),
            )
            for days in self.settings.analytics_pickup_days:
                cur.execute(
                    """
                    INSERT INTO opera_analytics.pickup_metric (
                        snapshot_date, comparison_days, hotel_id, stay_date, market_code,
                        channel_code, source_code, room_type, rate_code, rooms_on_books,
                        rooms_on_books_previous, pickup_rooms, room_revenue_on_books,
                        room_revenue_previous, pickup_room_revenue, total_revenue_on_books,
                        total_revenue_previous, pickup_total_revenue, adr_on_books, pickup_adr
                    )
                    SELECT
                        today.snapshot_date,
                        %s AS comparison_days,
                        today.hotel_id,
                        today.stay_date,
                        COALESCE(today.market_code, 'UNMAPPED'),
                        COALESCE(today.channel_code, 'UNMAPPED'),
                        COALESCE(today.source_code, 'UNMAPPED'),
                        COALESCE(today.room_type, 'UNMAPPED'),
                        COALESCE(today.rate_code, 'UNMAPPED'),
                        SUM(today.rooms),
                        SUM(COALESCE(old.rooms, 0)),
                        SUM(today.rooms - COALESCE(old.rooms, 0)),
                        SUM(today.room_revenue),
                        SUM(COALESCE(old.room_revenue, 0)),
                        SUM(today.room_revenue - COALESCE(old.room_revenue, 0)),
                        SUM(today.total_revenue),
                        SUM(COALESCE(old.total_revenue, 0)),
                        SUM(today.total_revenue - COALESCE(old.total_revenue, 0)),
                        CASE WHEN SUM(today.rooms) = 0 THEN NULL
                             ELSE SUM(today.room_revenue) / SUM(today.rooms)
                        END,
                        CASE WHEN SUM(today.rooms - COALESCE(old.rooms, 0)) = 0 THEN NULL
                             ELSE SUM(today.room_revenue - COALESCE(old.room_revenue, 0))
                                  / SUM(today.rooms - COALESCE(old.rooms, 0))
                        END
                    FROM opera_analytics.reservation_daily_snapshot today
                    LEFT JOIN opera_analytics.reservation_daily_snapshot old
                      ON old.hotel_id = today.hotel_id
                     AND old.reservation_id = today.reservation_id
                     AND old.stay_date = today.stay_date
                     AND old.snapshot_date = today.snapshot_date - (%s || ' days')::interval
                    WHERE today.snapshot_date = %s
                    GROUP BY
                        today.snapshot_date,
                        today.hotel_id,
                        today.stay_date,
                        COALESCE(today.market_code, 'UNMAPPED'),
                        COALESCE(today.channel_code, 'UNMAPPED'),
                        COALESCE(today.source_code, 'UNMAPPED'),
                        COALESCE(today.room_type, 'UNMAPPED'),
                        COALESCE(today.rate_code, 'UNMAPPED')
                    """,
                    (days, days, snapshot_date),
                )
        logger.info("analytics pickup metrics refreshed", extra={"snapshot_date": snapshot_date})


def main() -> None:
    settings = AnalyticsSettings()
    configure_logging(settings.log_level)
    AnalyticsSnapshotJob(settings).run()


if __name__ == "__main__":
    main()
