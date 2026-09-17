from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class OhipEvent:
    unique_event_id: str
    hotel_id: str
    module: str | None
    action_type: str | None
    occurred_at: datetime
    payload: dict[str, Any]
    offset: str | None = None

    @property
    def fifo_deduplication_id(self) -> str:
        return self.unique_event_id

    @property
    def raw_key_suffix(self) -> str:
        day = self.occurred_at.strftime("%Y/%m/%d")
        digest = hashlib.sha256(self.unique_event_id.encode("utf-8")).hexdigest()[:12]
        return f"hotel_id={self.hotel_id}/{day}/{self.unique_event_id}-{digest}.json"


def stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _find_first(payload: Any, names: set[str]) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in names and value not in (None, ""):
                return value
        for value in payload.values():
            found = _find_first(value, names)
            if found not in (None, ""):
                return found
    if isinstance(payload, list):
        for item in payload:
            found = _find_first(item, names)
            if found not in (None, ""):
                return found
    return None


def parse_ohip_event(payload: dict[str, Any]) -> OhipEvent:
    unique_event_id = str(
        _find_first(payload, {"uniqueEventId", "unique_event_id", "businessEventId", "eventId"})
        or hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()
    )
    hotel_id = str(
        _find_first(payload, {"hotelId", "hotelID", "resort", "propertyCode", "hotelCode"})
        or "UNKNOWN"
    )
    module = _find_first(payload, {"moduleName", "module", "eventType"})
    action_type = _find_first(payload, {"actionType", "action", "eventName"})
    offset = _find_first(payload, {"offset", "cursor", "sequence", "sequenceNumber"})
    occurred_raw = _find_first(
        payload, {"timestamp", "createdDateTime", "creationDate", "eventTime"}
    )
    occurred_at = _parse_datetime(occurred_raw)
    return OhipEvent(
        unique_event_id=unique_event_id,
        hotel_id=hotel_id,
        module=str(module) if module else None,
        action_type=str(action_type) if action_type else None,
        occurred_at=occurred_at,
        payload=payload,
        offset=str(offset) if offset else None,
    )


def _parse_datetime(value: Any) -> datetime:
    if not value:
        return datetime.now(UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), UTC)
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
