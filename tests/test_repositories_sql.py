from ohip_bridge.enrichment_repositories import EventRepository


class FakeCursor:
    def __init__(self) -> None:
        self.statements = []

    def execute(self, statement, params=()):
        self.statements.append(statement)


def test_reservation_upsert_guards_against_older_events(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().upsert_reservation(
        cur,
        {
            "hotel_id": "MAD01",
            "reservation_id": "resv-1",
            "confirmation_no": "ABC",
            "arrival_date": None,
            "departure_date": None,
            "reservation_status": "Reserved",
        },
        sample_event,
    )

    sql = "\n".join(cur.statements)
    assert "ON CONFLICT (hotel_id, reservation_id) DO UPDATE" in sql
    assert "last_event_at <= EXCLUDED.last_event_at" in sql
