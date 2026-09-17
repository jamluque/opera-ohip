from pathlib import Path

import pytest

from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolver
from ohip_bridge.opera_event_parser import OperaEventParser

ROUTER_PATH = Path("config/event-router.yaml")


def test_router_resolves_reservation_route() -> None:
    event = OperaEventParser().parse(
        {
            "uniqueEventId": "evt-1",
            "moduleName": "Reservation",
            "eventName": "NewReservation",
            "hotelId": "MAD01",
            "primaryKey": "resv-1",
        }
    )

    route = EventRouter.from_yaml(ROUTER_PATH).route_for(event)

    assert route is not None
    assert route.operation_id == "getReservation"
    assert route.identifier_type == "reservationId"


def test_financial_transaction_uses_transaction_no_not_unique_event_id() -> None:
    event = OperaEventParser().parse(
        {
            "uniqueEventId": "evt-dedup-only",
            "moduleName": "Cashiering",
            "eventName": "Transaction",
            "hotelId": "MAD01",
            "primaryKey": "998877",
        }
    )
    route = EventRouter.from_yaml(ROUTER_PATH).route_for(event)
    resolved = IdentifierResolver().resolve(event, route)  # type: ignore[arg-type]

    assert route.operation_id == "getFolioTransactionDetails"  # type: ignore[union-attr]
    assert resolved.identifier_type == "transactionNo"
    assert resolved.value == "998877"
    assert resolved.value != event.unique_event_id


def test_folio_reservation_id_can_come_from_detail() -> None:
    event = OperaEventParser().parse(
        {
            "uniqueEventId": "evt-2",
            "moduleName": "Cashiering",
            "eventName": "Folio",
            "hotelId": "MAD01",
            "primaryKey": "folio-123",
            "detail": [{"elementName": "reservationId", "newValue": "resv-777"}],
        }
    )
    route = EventRouter.from_yaml(ROUTER_PATH).route_for(event)
    resolved = IdentifierResolver().resolve(event, route)  # type: ignore[arg-type]

    assert resolved.identifier_type == "reservationId"
    assert resolved.value == "resv-777"


def test_unresolvable_identifier_raises() -> None:
    event = OperaEventParser().parse(
        {
            "uniqueEventId": "evt-3",
            "moduleName": "Profile",
            "eventName": "UpdateProfile",
            "hotelId": "MAD01",
        }
    )
    route = EventRouter.from_yaml(ROUTER_PATH).route_for(event)

    with pytest.raises(ValueError):
        IdentifierResolver().resolve(event, route)  # type: ignore[arg-type]
