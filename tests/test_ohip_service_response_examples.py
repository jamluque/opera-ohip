import json
from pathlib import Path

from ohip_bridge.transformers import FolioTransformer, ProfileTransformer, ReservationTransformer

EXAMPLES = Path("examples/ohip-service-api-responses")


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_service_response_examples_feed_core_upserts() -> None:
    reservation = ReservationTransformer().transform(
        load("get-reservation-response.json"), hotel_id="MAD01", reservation_id="resv-10001"
    )
    assert reservation == {
        "hotel_id": "MAD01",
        "reservation_id": "resv-10001",
        "confirmation_no": "CNF10001",
        "arrival_date": "2026-09-02",
        "departure_date": "2026-09-05",
        "reservation_status": "RESERVED",
        "source_updated_at": "2026-08-17T10:16:10Z",
    }

    profile = ProfileTransformer().transform(load("get-profile-response.json"), profile_id="p-9001")
    assert profile == {
        "profile_id": "p-9001",
        "profile_type": "GUEST",
        "first_name": "Lucia",
        "last_name": "Martin",
        "email": "lucia.martin@example.invalid",
        "source_updated_at": "2026-08-17T11:21:30Z",
    }

    folios = FolioTransformer().transform_folios(
        load("get-folios-response.json"), hotel_id="MAD01", reservation_id="resv-10001"
    )
    assert folios == [
        {
            "hotel_id": "MAD01",
            "reservation_id": "resv-10001",
            "folio_id": "folio-1",
            "folio_no": "101",
            "balance_amount": "248.50",
            "currency_code": "EUR",
            "source_updated_at": "2026-08-17T13:05:00Z",
        }
    ]

    transaction = FolioTransformer().transform_transaction(
        load("get-transaction-details-response.json"),
        hotel_id="MAD01",
        transaction_no="900001",
    )
    assert transaction == {
        "hotel_id": "MAD01",
        "transaction_no": "900001",
        "reservation_id": "resv-10001",
        "folio_id": "folio-1",
        "amount": "120.00",
        "currency_code": "EUR",
        "transaction_code": "ROOM",
        "source_updated_at": "2026-08-17T14:11:20Z",
    }


def test_cancel_404_example_matches_deleted_marker_payload() -> None:
    assert load("reservation-cancel-404-deleted-marker.json") == {
        "deleted": True,
        "resource_id": "resv-10003",
    }
