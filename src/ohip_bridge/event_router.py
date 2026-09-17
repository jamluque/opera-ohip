from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ohip_bridge.opera_event_parser import OperaBusinessEvent


@dataclass(frozen=True)
class EventRoute:
    module_name: str
    event_name: str
    resource_type: str
    operation_id: str
    method: str
    path: str
    identifier_type: str
    fetch: str


class EventRouter:
    def __init__(self, routes: list[EventRoute], aliases: dict[str, dict[str, str]]) -> None:
        self.routes = routes
        self.aliases = aliases

    @classmethod
    def from_yaml(cls, path: str | Path) -> EventRouter:
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        routes = [
            EventRoute(
                module_name=item["moduleName"],
                event_name=item["eventName"],
                resource_type=item["resource_type"],
                operation_id=item["operation_id"],
                method=item.get("method", "GET"),
                path=item["path"],
                identifier_type=item["identifier_type"],
                fetch=item["fetch"],
            )
            for item in payload.get("routes", [])
        ]
        return cls(routes=routes, aliases=payload.get("aliases", {}))

    def route_for(self, event: OperaBusinessEvent) -> EventRoute | None:
        module_name = self._normalize("moduleName", event.module_name)
        event_name = self._normalize("eventName", event.event_name)
        for route in self.routes:
            if route.module_name == module_name and route.event_name == event_name:
                return route
        for route in self.routes:
            if route.module_name == module_name and route.event_name == "*":
                return route
        return None

    def _normalize(self, kind: str, value: str | None) -> str | None:
        if value is None:
            return None
        aliases: dict[str, Any] = self.aliases.get(kind, {})
        return aliases.get(value, aliases.get(value.upper(), value))
