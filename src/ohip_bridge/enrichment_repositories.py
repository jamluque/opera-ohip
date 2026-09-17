from __future__ import annotations

from datetime import datetime
from typing import Any

from ohip_bridge.events import stable_json
from ohip_bridge.opera_event_parser import OperaBusinessEvent


class EventRepository:
    def register_event(self, cur: Any, event: OperaBusinessEvent) -> str:
        cur.execute(
            """
            INSERT INTO opera_events.event (
                unique_event_id, chain_code, hotel_id, stream_offset, primary_key,
                module_name, event_name, occurred_at, payload, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'RECEIVED')
            ON CONFLICT DO NOTHING
            """,
            (
                event.unique_event_id,
                event.chain_code,
                event.hotel_id,
                event.offset,
                event.primary_key,
                event.module_name,
                event.event_name,
                event.occurred_at,
                stable_json(event.payload),
            ),
        )
        cur.execute(
            """
            SELECT status FROM opera_events.event
             WHERE unique_event_id = %s
                OR (chain_code = %s AND stream_offset = %s)
             ORDER BY CASE WHEN unique_event_id = %s THEN 0 ELSE 1 END
             LIMIT 1
            """,
            (event.unique_event_id, event.chain_code, event.offset, event.unique_event_id),
        )
        row = cur.fetchone()
        return row["status"] if isinstance(row, dict) else row[0]

    def mark_completed(self, cur: Any, unique_event_id: str) -> None:
        cur.execute(
            """
            UPDATE opera_events.event
               SET status = 'COMPLETED', completed_at = now(), error_message = NULL
             WHERE unique_event_id = %s
            """,
            (unique_event_id,),
        )

    def mark_failed(self, cur: Any, unique_event_id: str, status: str, error_message: str) -> None:
        cur.execute(
            """
            UPDATE opera_events.event
               SET status = %s, error_message = %s, failed_at = now(), retry_count = retry_count + 1
             WHERE unique_event_id = %s
            """,
            (status, error_message[:2000], unique_event_id),
        )

    def upsert_reservation(self, cur: Any, row: dict[str, Any], event: OperaBusinessEvent) -> None:
        cur.execute(
            """
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
            """,
            (
                row["hotel_id"],
                row["reservation_id"],
                row.get("confirmation_no"),
                row.get("arrival_date"),
                row.get("departure_date"),
                row.get("reservation_status"),
                self._dt(row.get("source_updated_at")),
                event.unique_event_id,
                event.occurred_at,
            ),
        )

    def upsert_profile(self, cur: Any, row: dict[str, Any], event: OperaBusinessEvent) -> None:
        cur.execute(
            """
            INSERT INTO opera_core.profile (
                profile_id, profile_type, first_name, last_name, email,
                source_updated_at, last_event_id, last_event_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (profile_id) DO UPDATE SET
                profile_type = EXCLUDED.profile_type,
                first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                email = EXCLUDED.email,
                source_updated_at = EXCLUDED.source_updated_at,
                last_event_id = EXCLUDED.last_event_id,
                last_event_at = EXCLUDED.last_event_at,
                updated_at = now()
            WHERE opera_core.profile.last_event_at IS NULL
               OR opera_core.profile.last_event_at <= EXCLUDED.last_event_at
            """,
            (
                row["profile_id"],
                row.get("profile_type"),
                row.get("first_name"),
                row.get("last_name"),
                row.get("email"),
                self._dt(row.get("source_updated_at")),
                event.unique_event_id,
                event.occurred_at,
            ),
        )

    def upsert_folio(self, cur: Any, row: dict[str, Any], event: OperaBusinessEvent) -> None:
        cur.execute(
            """
            INSERT INTO opera_core.folio (
                hotel_id, reservation_id, folio_id, folio_no, balance_amount,
                currency_code, source_updated_at, last_event_id, last_event_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hotel_id, reservation_id, folio_id) DO UPDATE SET
                folio_no = EXCLUDED.folio_no,
                balance_amount = EXCLUDED.balance_amount,
                currency_code = EXCLUDED.currency_code,
                source_updated_at = EXCLUDED.source_updated_at,
                last_event_id = EXCLUDED.last_event_id,
                last_event_at = EXCLUDED.last_event_at,
                updated_at = now()
            WHERE opera_core.folio.last_event_at IS NULL
               OR opera_core.folio.last_event_at <= EXCLUDED.last_event_at
            """,
            (
                row["hotel_id"],
                row["reservation_id"],
                row["folio_id"],
                row.get("folio_no"),
                row.get("balance_amount"),
                row.get("currency_code"),
                self._dt(row.get("source_updated_at")),
                event.unique_event_id,
                event.occurred_at,
            ),
        )

    def upsert_folio_transaction(
        self, cur: Any, row: dict[str, Any], event: OperaBusinessEvent
    ) -> None:
        cur.execute(
            """
            INSERT INTO opera_core.folio_transaction (
                hotel_id, transaction_no, reservation_id, folio_id, amount, currency_code,
                transaction_code, source_updated_at, last_event_id, last_event_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (hotel_id, transaction_no) DO UPDATE SET
                reservation_id = EXCLUDED.reservation_id,
                folio_id = EXCLUDED.folio_id,
                amount = EXCLUDED.amount,
                currency_code = EXCLUDED.currency_code,
                transaction_code = EXCLUDED.transaction_code,
                source_updated_at = EXCLUDED.source_updated_at,
                last_event_id = EXCLUDED.last_event_id,
                last_event_at = EXCLUDED.last_event_at,
                updated_at = now()
            WHERE opera_core.folio_transaction.last_event_at IS NULL
               OR opera_core.folio_transaction.last_event_at <= EXCLUDED.last_event_at
            """,
            (
                row["hotel_id"],
                row["transaction_no"],
                row.get("reservation_id"),
                row.get("folio_id"),
                row.get("amount"),
                row.get("currency_code"),
                row.get("transaction_code"),
                self._dt(row.get("source_updated_at")),
                event.unique_event_id,
                event.occurred_at,
            ),
        )

    def _dt(self, value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None


class RawSnapshotRepository:
    def save(
        self,
        cur: Any,
        *,
        event: OperaBusinessEvent,
        resource_type: str,
        resource_id: str,
        operation_id: str,
        payload: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO opera_raw.resource_snapshot (
                unique_event_id, hotel_id, resource_type, resource_id, operation_id, payload
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (unique_event_id, resource_type, resource_id) DO UPDATE SET
                operation_id = EXCLUDED.operation_id,
                payload = EXCLUDED.payload,
                fetched_at = now()
            """,
            (
                event.unique_event_id,
                event.hotel_id,
                resource_type,
                resource_id,
                operation_id,
                stable_json(payload),
            ),
        )
