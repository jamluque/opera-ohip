from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ohip_bridge.events import stable_json


@dataclass(frozen=True)
class OperaBusinessEvent:
    unique_event_id: str
    offset: str | None
    primary_key: str | None
    module_name: str | None
    event_name: str | None
    hotel_id: str
    chain_code: str | None
    occurred_at: datetime
    details: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def is_delete_or_cancel(self) -> bool:
        text = f"{self.event_name or ''} {self.metadata.get('actionType') or ''}".upper()
        return "DELETE" in text or "CANCEL" in text or "CANCELLED" in text


class OperaEventParser:
    def parse(self, message_body: dict[str, Any]) -> OperaBusinessEvent:
        payload = message_body.get("payload") if "payload" in message_body else message_body
        if not isinstance(payload, dict):
            payload = {"payload": payload}
        source = {**payload, **message_body}
        details = self._details(source)
        unique_event_id = str(
            self._first(
                source, details, "uniqueEventId", "unique_event_id", "businessEventId", "eventId"
            )
            or hashlib.sha256(stable_json(payload).encode()).hexdigest()
        )
        occurred_at = self._parse_datetime(
            self._first(
                source, details, "timestamp", "createdDateTime", "creationDate", "eventTime"
            )
        )
        return OperaBusinessEvent(
            unique_event_id=unique_event_id,
            offset=self._as_text(
                self._first(source, details, "offset", "stream_offset", "sequence")
            ),
            primary_key=self._as_text(
                self._first(source, details, "primaryKey", "primary_key", "primaryKeyValue")
            ),
            module_name=self._as_text(
                self._first(source, details, "moduleName", "module", "module_name")
            ),
            event_name=self._as_text(
                self._first(source, details, "eventName", "actionType", "action_type", "action")
            ),
            hotel_id=str(
                self._first(source, details, "hotelId", "hotelID", "hotel_id", "resort")
                or "UNKNOWN"
            ),
            chain_code=self._as_text(self._first(source, details, "chainCode", "chain_code")),
            occurred_at=occurred_at,
            details=details,
            metadata={
                key: value
                for key, value in source.items()
                if key not in {"payload", "detail", "details"}
                and not isinstance(value, (dict, list))
            },
            payload=payload,
        )

    def _first(self, payload: dict[str, Any], details: list[dict[str, Any]], *names: str) -> Any:
        found = self._find(payload, set(names))
        if found not in (None, ""):
            return found
        wanted = {name.lower() for name in names}
        for detail in details:
            element_name = str(detail.get("elementName") or detail.get("name") or "").lower()
            if element_name in wanted:
                return detail.get("newValue") or detail.get("oldValue") or detail.get("value")
        return None

    def _find(self, value: Any, names: set[str]) -> Any:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in names and item not in (None, ""):
                    return item
            for item in value.values():
                found = self._find(item, names)
                if found not in (None, ""):
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._find(item, names)
                if found not in (None, ""):
                    return found
        return None

    def _details(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        raw = (
            payload.get("detail")
            or payload.get("details")
            or self._find(payload, {"detail", "details"})
        )
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
        if isinstance(raw, dict):
            return [raw]
        return []

    def _parse_datetime(self, value: Any) -> datetime:
        if not value:
            return datetime.now(UTC)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), UTC)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(UTC)
        return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)

    def _as_text(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)
