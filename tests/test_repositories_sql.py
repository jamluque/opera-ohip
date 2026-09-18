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


def test_mark_resource_deleted_reservation(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().mark_resource_deleted(cur, "reservation", "resv-1", sample_event)

    sql = "\n".join(cur.statements)
    assert "INSERT INTO opera_core.reservation" in sql
    assert "deleted_at = now()" in sql
    assert "ON CONFLICT (hotel_id, reservation_id)" in sql
    assert "last_event_at <= EXCLUDED.last_event_at" in sql


def test_mark_resource_deleted_profile(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().mark_resource_deleted(cur, "profile", "prof-1", sample_event)

    sql = "\n".join(cur.statements)
    assert "opera_core.profile" in sql
    assert "ON CONFLICT (profile_id)" in sql


def test_mark_resource_deleted_folio_transaction(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().mark_resource_deleted(cur, "folio_transaction", "txn-1", sample_event)

    sql = "\n".join(cur.statements)
    assert "opera_core.folio_transaction" in sql
    assert "ON CONFLICT (hotel_id, transaction_no)" in sql


def test_mark_resource_deleted_folio_writes_nothing(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().mark_resource_deleted(cur, "folio", "resv-1", sample_event)

    assert cur.statements == []


def test_mark_deleted_sets_deleted_status(sample_event) -> None:
    cur = FakeCursor()
    EventRepository().mark_deleted(cur, sample_event.unique_event_id)

    sql = "\n".join(cur.statements)
    assert "status = 'DELETED'" in sql
