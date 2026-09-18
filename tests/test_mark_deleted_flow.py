from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

from ohip_bridge.enrichment_service import OperaEnrichmentService
from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolver


def _svc(evt_repo, raw_repo):
    settings = SimpleNamespace(
        database_url=SimpleNamespace(get_secret_value=lambda: "postgresql://x"),
        enricher_pool_max_size=5,
    )
    svc = OperaEnrichmentService(
        settings,
        EventRouter([], {}),
        IdentifierResolver(),
        None,
        event_repository=evt_repo,
        raw_repository=raw_repo,
    )

    @contextmanager
    def fake_conn():
        yield MagicMock()

    svc._conn = fake_conn
    return svc


def test_mark_deleted_marks_core_and_event(sample_event):
    evt = MagicMock()
    evt.register_event.return_value = "RECEIVED"
    raw = MagicMock()
    svc = _svc(evt, raw)
    result = svc._mark_deleted(sample_event, "reservation", "resv-1")
    raw.save.assert_called_once()
    evt.mark_resource_deleted.assert_called_once()
    assert evt.mark_resource_deleted.call_args.args[1:] == ("reservation", "resv-1", sample_event)
    evt.mark_deleted.assert_called_once()
    assert result.status == "DELETED" and result.deleted is True
