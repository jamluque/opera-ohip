from datetime import UTC, datetime

import pytest

from ohip_bridge.opera_event_parser import OperaBusinessEvent


@pytest.fixture
def sample_event() -> OperaBusinessEvent:
    return OperaBusinessEvent(
        unique_event_id="evt-1",
        offset="1",
        primary_key="resv-1",
        module_name="Reservation",
        event_name="Update",
        hotel_id="MAD01",
        chain_code="CHAIN",
        occurred_at=datetime(2026, 8, 3, tzinfo=UTC),
        payload={"uniqueEventId": "evt-1"},
    )
