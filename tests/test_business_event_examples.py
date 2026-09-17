import json
from pathlib import Path

from ohip_bridge.event_router import EventRouter
from ohip_bridge.identifier_resolver import IdentifierResolver
from ohip_bridge.opera_event_parser import OperaEventParser


def test_business_event_examples_are_consumable() -> None:
    parser = OperaEventParser()
    router = EventRouter.from_yaml("config/event-router.yaml")
    resolver = IdentifierResolver()

    paths = sorted(Path("examples/ohip-business-events").glob("*.json"))
    assert paths

    for path in paths:
        event = parser.parse(json.loads(path.read_text(encoding="utf-8")))
        route = router.route_for(event)

        assert route is not None, path
        assert resolver.resolve(event, route).value
