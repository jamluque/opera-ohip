from datetime import UTC, datetime

from ohip_bridge.events import parse_ohip_event, stable_json
from ohip_bridge.opera_event_parser import OperaBusinessEvent


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


def _event(**kw):
    base = dict(
        unique_event_id="e", offset=None, primary_key=None,
        module_name="Reservation", event_name="UpdateReservation",
        hotel_id="H", chain_code="C", occurred_at=datetime.now(UTC),
    )
    base.update(kw)
    return OperaBusinessEvent(**base)


def test_cancel_detected_from_detail_status():
    ev = _event(details=[{"elementName": "reservationStatus",
                          "oldValue": "RESERVED", "newValue": "CANCELLED"}])
    assert ev.is_delete_or_cancel is True


def test_deletion_detected_when_all_new_values_empty():
    ev = _event(details=[{"elementName": "x", "oldValue": "1", "newValue": ""}])
    assert ev.is_delete_or_cancel is True


def test_plain_update_not_flagged():
    ev = _event(details=[{"elementName": "roomType", "oldValue": "A", "newValue": "B"}])
    assert ev.is_delete_or_cancel is False
