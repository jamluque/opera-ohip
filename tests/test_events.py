from datetime import UTC

from ohip_bridge.events import parse_ohip_event, stable_json


def test_parse_ohip_event_extracts_identity_fields() -> None:
    event = parse_ohip_event(
        {
            "uniqueEventId": "evt-123",
            "hotelId": "MAD01",
            "moduleName": "Reservation",
            "actionType": "NEW RESERVATION",
            "creationDate": "2026-08-03T10:11:12Z",
            "offset": "42",
        }
    )

    assert event.unique_event_id == "evt-123"
    assert event.hotel_id == "MAD01"
    assert event.module == "Reservation"
    assert event.action_type == "NEW RESERVATION"
    assert event.offset == "42"
    assert event.occurred_at.tzinfo == UTC


def test_parse_ohip_event_falls_back_to_hash_when_no_unique_id() -> None:
    first = parse_ohip_event({"hotelId": "MAD01", "payload": {"a": 1, "b": 2}})
    second = parse_ohip_event({"payload": {"b": 2, "a": 1}, "hotelId": "MAD01"})

    assert first.unique_event_id == second.unique_event_id


def test_stable_json_is_deterministic() -> None:
    assert stable_json({"b": 2, "a": 1}) == stable_json({"a": 1, "b": 2})
