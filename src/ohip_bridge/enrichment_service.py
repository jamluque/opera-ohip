from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ohip_bridge import metrics
from ohip_bridge.config import Settings
from ohip_bridge.enrichment_repositories import EventRepository, RawSnapshotRepository
from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolutionError, IdentifierResolver
from ohip_bridge.ohip_client import OHIPClient, OHIPHTTPError, OHIPResponse
from ohip_bridge.opera_event_parser import OperaBusinessEvent
from ohip_bridge.retry_classifier import RetryClassifier, RetryDecision
from ohip_bridge.transformers import FolioTransformer, ProfileTransformer, ReservationTransformer

logger = logging.getLogger(__name__)


class EnrichmentRetryableError(RuntimeError):
    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class EnrichmentPoisonError(RuntimeError):
    pass


@dataclass(frozen=True)
class EnrichmentResult:
    unique_event_id: str
    status: str
    deduplicated: bool = False
    deleted: bool = False


class OperaEnrichmentService:
    def __init__(
        self,
        settings: Settings,
        router: EventRouter,
        resolver: IdentifierResolver,
        ohip_client: OHIPClient,
        event_repository: EventRepository | None = None,
        raw_repository: RawSnapshotRepository | None = None,
    ) -> None:
        self.settings = settings
        self.router = router
        self.resolver = resolver
        self.ohip_client = ohip_client
        self.event_repository = event_repository or EventRepository()
        self.raw_repository = raw_repository or RawSnapshotRepository()
        self.retry_classifier = RetryClassifier()
        self.reservation_transformer = ReservationTransformer()
        self.profile_transformer = ProfileTransformer()
        self.folio_transformer = FolioTransformer()
        self._pool = ConnectionPool(
            self.settings.database_url.get_secret_value(),
            min_size=1,
            max_size=self.settings.enricher_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
        )

    async def enrich(self, event: OperaBusinessEvent) -> EnrichmentResult:
        route = self.router.route_for(event)
        if not route:
            raise EnrichmentPoisonError(
                f"No route for moduleName={event.module_name} eventName={event.event_name}"
            )
        try:
            resolved = self.resolver.resolve(event, route)
        except IdentifierResolutionError as exc:
            metrics.unresolvable_identifiers.inc()
            raise EnrichmentPoisonError(str(exc)) from exc

        try:
            response = await self._fetch(event, route.operation_id, resolved.value)
        except OHIPHTTPError as exc:
            classification = self.retry_classifier.classify_http(
                exc.status_code, is_delete_or_cancel=event.is_delete_or_cancel
            )
            if classification.decision == RetryDecision.DELETED:
                return self._mark_deleted(event, route.resource_type, resolved.value)
            if classification.decision == RetryDecision.RETRY:
                metrics.messages_retried.inc()
                raise EnrichmentRetryableError(str(exc), exc.retry_after) from exc
            raise EnrichmentPoisonError(str(exc)) from exc

        return self._persist(event, route.resource_type, resolved.value, response)

    async def _fetch(
        self, event: OperaBusinessEvent, operation_id: str, identifier: str
    ) -> OHIPResponse:
        if operation_id == "getReservation":
            return await self.ohip_client.get_reservation(event.hotel_id, identifier)
        if operation_id == "getProfile":
            return await self.ohip_client.get_profile(identifier, event.hotel_id)
        if operation_id == "getFolio":
            return await self.ohip_client.get_folios(event.hotel_id, identifier)
        if operation_id == "getFolioTransactionDetails":
            return await self.ohip_client.get_transaction_details(event.hotel_id, identifier)
        raise EnrichmentPoisonError(f"Unsupported operation_id={operation_id}")

    def _conn(self):
        return self._pool.connection()

    def _persist(
        self,
        event: OperaBusinessEvent,
        resource_type: str,
        resource_id: str,
        response: OHIPResponse,
    ) -> EnrichmentResult:
        with self._conn() as conn:
            try:
                with conn.cursor() as cur:
                    status = self.event_repository.register_event(cur, event)
                    if status == "COMPLETED":
                        conn.commit()
                        metrics.events_deduplicated.inc()
                        return EnrichmentResult(event.unique_event_id, status, deduplicated=True)
                    self.raw_repository.save(
                        cur,
                        event=event,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        operation_id=response.operation_id,
                        payload=response.payload,
                    )
                    self._upsert_core(cur, event, resource_type, resource_id, response.payload)
                    self.event_repository.mark_completed(cur, event.unique_event_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        metrics.events_enriched.inc()
        return EnrichmentResult(event.unique_event_id, "COMPLETED")

    def _mark_deleted(
        self, event: OperaBusinessEvent, resource_type: str, resource_id: str
    ) -> EnrichmentResult:
        with self._conn() as conn:
            with conn.cursor() as cur:
                status = self.event_repository.register_event(cur, event)
                if status == "COMPLETED":
                    conn.commit()
                    metrics.events_deduplicated.inc()
                    return EnrichmentResult(event.unique_event_id, status, deduplicated=True)
                self.raw_repository.save(
                    cur,
                    event=event,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    operation_id="deleted_marker",
                    payload={"deleted": True, "resource_id": resource_id},
                )
                self.event_repository.mark_resource_deleted(cur, resource_type, resource_id, event)
                self.event_repository.mark_deleted(cur, event.unique_event_id)
            conn.commit()
        return EnrichmentResult(event.unique_event_id, "DELETED", deleted=True)

    def mark_failed(self, event: OperaBusinessEvent, status: str, error_message: str) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                self.event_repository.register_event(cur, event)
                self.event_repository.mark_failed(cur, event.unique_event_id, status, error_message)
            conn.commit()

    def _upsert_core(
        self,
        cur: Any,
        event: OperaBusinessEvent,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any],
    ) -> None:
        if resource_type == "reservation":
            row = self.reservation_transformer.transform(
                payload, hotel_id=event.hotel_id, reservation_id=resource_id
            )
            self.event_repository.upsert_reservation(cur, row, event)
            return
        if resource_type == "profile":
            row = self.profile_transformer.transform(payload, profile_id=resource_id)
            self.event_repository.upsert_profile(cur, row, event)
            return
        if resource_type == "folio":
            rows = self.folio_transformer.transform_folios(
                payload, hotel_id=event.hotel_id, reservation_id=resource_id
            )
            for row in rows:
                self.event_repository.upsert_folio(cur, row, event)
            return
        if resource_type == "folio_transaction":
            row = self.folio_transformer.transform_transaction(
                payload, hotel_id=event.hotel_id, transaction_no=resource_id
            )
            self.event_repository.upsert_folio_transaction(cur, row, event)
            return
        raise EnrichmentPoisonError(f"Unsupported resource_type={resource_type}")
