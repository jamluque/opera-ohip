from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ohip_bridge.event_router import EventRoute
from ohip_bridge.opera_event_parser import OperaBusinessEvent


class IdentifierResolutionError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedIdentifier:
    identifier_type: str
    value: str


class IdentifierResolver:
    CANDIDATES = {
        "reservationId": [
            "reservationId",
            "reservationID",
            "resvId",
            "resvNameId",
            "confirmationNo",
        ],
        "transactionNo": ["transactionNo", "transactionNumber", "transactionId", "trxNo"],
        "profileId": ["profileId", "profileID", "profileNo", "nameId"],
        "primaryKey": ["primaryKey", "primary_key"],
    }

    def resolve(self, event: OperaBusinessEvent, route: EventRoute) -> ResolvedIdentifier:
        identifier_type = route.identifier_type
        value = self._resolve_value(event, identifier_type, route.resource_type)
        if not value:
            raise IdentifierResolutionError(
                f"Could not resolve {identifier_type} for event {event.unique_event_id}"
            )
        return ResolvedIdentifier(identifier_type=identifier_type, value=value)

    def _resolve_value(
        self, event: OperaBusinessEvent, identifier_type: str, resource_type: str
    ) -> str | None:
        names = self.CANDIDATES.get(identifier_type, [identifier_type])
        prefer_detail = resource_type == "folio" and identifier_type == "reservationId"
        if not prefer_detail and identifier_type in {
            "reservationId",
            "transactionNo",
            "profileId",
            "primaryKey",
        }:
            direct = self._matching_primary_key(event.primary_key, identifier_type)
            if direct:
                return direct
        metadata = self._from_mapping(event.metadata, names)
        if metadata:
            return metadata
        detail = self._from_details(event.details, names)
        if detail:
            return detail
        payload = self._from_mapping(event.payload, names)
        if payload:
            return payload
        if prefer_detail:
            return None
        return event.primary_key if identifier_type == "primaryKey" else None

    def _matching_primary_key(self, primary_key: str | None, identifier_type: str) -> str | None:
        if not primary_key:
            return None
        if identifier_type == "transactionNo" and not re.search(r"\d", primary_key):
            return None
        return primary_key

    def _from_details(self, details: list[dict[str, Any]], names: list[str]) -> str | None:
        wanted = {name.lower() for name in names}
        for detail in details:
            element_name = str(detail.get("elementName") or detail.get("name") or "").lower()
            if element_name in wanted:
                value = detail.get("newValue") or detail.get("oldValue") or detail.get("value")
                if value not in (None, ""):
                    return str(value)
        return None

    def _from_mapping(self, payload: Any, names: list[str]) -> str | None:
        wanted = set(names)
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in wanted and value not in (None, ""):
                    return str(value)
            for value in payload.values():
                found = self._from_mapping(value, names)
                if found:
                    return found
        if isinstance(payload, list):
            for item in payload:
                found = self._from_mapping(item, names)
                if found:
                    return found
        return None
