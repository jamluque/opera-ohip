from datetime import UTC, datetime

from ohip_bridge.consumer import _event_from_message


def test_event_from_message_round_trip() -> None:
    event = _event_from_message(
        {
            "unique_event_id": "evt-123",
            "hotel_id": "MAD01",
            "module": "Reservation",
            "action_type": "UPDATE RESERVATION",
            "occurred_at": "2026-08-03T10:11:12+00:00",
            "payload": {"uniqueEventId": "evt-123"},
            "offset": "99",
        }
    )

    assert event.unique_event_id == "evt-123"
    assert event.hotel_id == "MAD01"
    assert event.occurred_at == datetime(2026, 8, 3, 10, 11, 12, tzinfo=UTC)
