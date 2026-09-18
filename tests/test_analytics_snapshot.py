from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

from ohip_bridge.analytics_snapshot import AnalyticsSnapshotJob, ReservationSnapshotTransformer


def test_reservation_snapshot_expands_stay_dates_and_extracts_payload_fields() -> None:
    row = {
        "hotel_id": "MAD01",
        "reservation_id": "resv-1",
        "confirmation_no": "ABC123",
        "arrival_date": date(2026, 8, 10),
        "departure_date": date(2026, 8, 13),
        "reservation_status": "RESERVED",
        "source_updated_at": None,
        "last_event_id": "evt-1",
        "last_event_at": None,
        "raw_payload": {
            "roomType": "DLX",
            "rateCode": "BAR",
            "marketCode": "CORP",
            "sourceCode": "WEB",
            "channelCode": "DIRECT",
            "dailyRates": [
                {"stayDate": "2026-08-10", "roomRevenue": "100.00"},
                {"stayDate": "2026-08-11", "roomRevenue": "120.00"},
                {"stayDate": "2026-08-12", "roomRevenue": "130.00"},
            ],
        },
    }

    rows = ReservationSnapshotTransformer().transform(row, date(2026, 8, 9))

    assert [item.stay_date for item in rows] == [
        date(2026, 8, 10),
        date(2026, 8, 11),
        date(2026, 8, 12),
    ]
    assert rows[0].room_type == "DLX"
    assert rows[0].rate_code == "BAR"
    assert rows[0].room_revenue == Decimal("100.00")
    assert rows[1].room_revenue == Decimal("120.00")


def test_reservation_snapshot_carries_deleted_at() -> None:
    deleted_at = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
    row = {
        "hotel_id": "MAD01",
        "reservation_id": "resv-1",
        "arrival_date": date(2026, 8, 10),
        "departure_date": date(2026, 8, 11),
        "deleted_at": deleted_at,
        "raw_payload": {},
    }

    rows = ReservationSnapshotTransformer().transform(row, date(2026, 8, 9))

    assert rows[0].deleted_at == deleted_at


def test_reservation_snapshot_skips_past_stay_dates() -> None:
    row = {
        "hotel_id": "MAD01",
        "reservation_id": "resv-1",
        "arrival_date": date(2026, 8, 1),
        "departure_date": date(2026, 8, 4),
        "raw_payload": {},
    }

    rows = ReservationSnapshotTransformer().transform(row, date(2026, 8, 3))

    assert [item.stay_date for item in rows] == [date(2026, 8, 3)]
    assert rows[0].rooms == Decimal("1")
    assert rows[0].room_revenue == Decimal("0")


class RecordingCursor:
    def __init__(self) -> None:
        self.executions: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self) -> "RecordingCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executions.append((" ".join(sql.split()), params))


class RecordingConnection:
    def __init__(self) -> None:
        self.cursor_instance = RecordingCursor()

    def cursor(self) -> RecordingCursor:
        return self.cursor_instance


def test_last_status_refresh_materializes_one_row_per_reservation_without_status_filter() -> None:
    conn = RecordingConnection()
    job = AnalyticsSnapshotJob.__new__(AnalyticsSnapshotJob)

    job._refresh_last_status(conn, date(2026, 8, 11))

    executed_sql = "\n".join(sql for sql, _ in conn.cursor_instance.executions)
    assert conn.cursor_instance.executions[0] == ("SET LOCAL work_mem = '256MB'", ())
    assert "opera_analytics.reservation_last_status_daily" in executed_sql
    assert "ROW_NUMBER() OVER" in executed_sql
    assert "reservation_bounds" not in executed_sql
    assert "ON CONFLICT (snapshot_date, hotel_id, reservation_id)" in executed_sql
    assert "reservation_status NOT IN" not in executed_sql
    assert "CANCELLED" not in executed_sql
    assert "NO_SHOW" not in executed_sql
    assert conn.cursor_instance.executions[1][1] == (date(2026, 8, 11),)
    assert conn.cursor_instance.executions[2][1] == (date(2026, 8, 11),)


def test_last_status_refresh_marks_deleted_reservations() -> None:
    conn = RecordingConnection()
    job = AnalyticsSnapshotJob.__new__(AnalyticsSnapshotJob)

    job._refresh_last_status(conn, date(2026, 8, 11))

    executed_sql = "\n".join(sql for sql, _ in conn.cursor_instance.executions)
    assert (
        "CASE WHEN status.deleted_at IS NOT NULL THEN 'DELETED' ELSE status.reservation_status END"
        in executed_sql
    )


def test_pickups_refresh_excludes_deleted_and_cancelled_no_show() -> None:
    conn = RecordingConnection()
    job = AnalyticsSnapshotJob.__new__(AnalyticsSnapshotJob)
    job.settings = SimpleNamespace(analytics_pickup_days=[7])

    job._refresh_pickups(conn, date(2026, 8, 11))

    executed_sql = "\n".join(sql for sql, _ in conn.cursor_instance.executions)
    assert "today.deleted_at IS NULL" in executed_sql
    assert "NOT IN ('CANCELLED', 'NO_SHOW')" in executed_sql
