from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import websockets

from ohip_bridge.config import Settings
from ohip_bridge.events import parse_ohip_event
from ohip_bridge.oauth import OAuthClient

logger = logging.getLogger(__name__)


class OhipStreamingClient:
    def __init__(self, settings: Settings, oauth: OAuthClient) -> None:
        self.settings = settings
        self.oauth = oauth

    def _websocket_url(self) -> str:
        app_key_hash = hashlib.sha256(
            self.settings.ohip_application_key.get_secret_value().encode("utf-8")
        ).hexdigest()
        separator = "&" if "?" in self.settings.ohip_streaming_ws_url else "?"
        return f"{self.settings.ohip_streaming_ws_url}{separator}{urlencode({'key': app_key_hash})}"

    async def events(self, offset: dict[str, Any] | None = None) -> AsyncIterator[dict[str, Any]]:
        token = await self.oauth.token()
        headers = {"Sec-WebSocket-Protocol": "graphql-transport-ws"}
        subscription_id = str(uuid.uuid4())

        async with websockets.connect(
            self._websocket_url(),
            subprotocols=["graphql-transport-ws"],
            extra_headers=headers,
            ping_interval=None,
            close_timeout=10,
            max_size=16 * 1024 * 1024,
        ) as websocket:
            await websocket.send(json.dumps(self._connection_init_payload(token.access_token)))
            await self._wait_for_ack(websocket)
            await websocket.send(
                json.dumps(
                    {
                        "id": subscription_id,
                        "type": "subscribe",
                        "payload": {
                            "query": self._subscription_query(offset),
                            "variables": {},
                            "extensions": {},
                            "operationName": None,
                        },
                    }
                )
            )
            heartbeat = asyncio.create_task(self._heartbeat(websocket))
            try:
                async for raw_message in websocket:
                    message = json.loads(raw_message)
                    message_type = message.get("type")
                    if message_type == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
                        continue
                    if message_type == "pong":
                        continue
                    if message_type == "next":
                        for payload in self._extract_payloads(message.get("payload", {})):
                            yield payload
                    elif message_type == "error":
                        raise RuntimeError(f"OHIP subscription error: {message.get('payload')}")
                    elif message_type == "complete":
                        logger.warning("OHIP subscription completed by server")
                        return
            finally:
                heartbeat.cancel()
                with suppress(Exception):
                    await websocket.send(self._complete_message(subscription_id))

    def _subscription_query(self, offset: dict[str, Any] | None = None) -> str:
        if self.settings.ohip_subscription_query_file:
            return Path(self.settings.ohip_subscription_query_file).read_text(encoding="utf-8")
        offset_part = f' offset: "{offset["offset"]}"' if offset and offset.get("offset") else ""
        return (
            "subscription { "
            f'newEvent(input: {{ chainCode: "{self.settings.ohip_chain_code}"{offset_part} }}) '
            "{ metadata { offset uniqueEventId } moduleName eventName primaryKey timestamp "
            "hotelId publisherId actionInstanceId detail { oldValue newValue elementName "
            "scopeFrom scopeTo elementType elementRole elementSequence } } }"
        )

    def _connection_init_payload(self, access_token: str) -> dict[str, Any]:
        return {
            "type": "connection_init",
            "payload": {
                "Authorization": f"Bearer {access_token}",
                "x-app-key": self.settings.ohip_application_key.get_secret_value(),
            },
        }

    def _complete_message(self, subscription_id: str) -> str:
        return json.dumps({"id": subscription_id, "type": "complete"})

    async def _wait_for_ack(self, websocket: websockets.WebSocketClientProtocol) -> None:
        deadline = time.time() + 20
        while time.time() < deadline:
            message = json.loads(await websocket.recv())
            if message.get("type") == "connection_ack":
                return
            if message.get("type") == "ping":
                await websocket.send(json.dumps({"type": "pong"}))
            elif message.get("type") == "error":
                raise RuntimeError(f"OHIP connection error: {message.get('payload')}")
        raise TimeoutError("Timed out waiting for OHIP connection_ack")

    async def _heartbeat(self, websocket: websockets.WebSocketClientProtocol) -> None:
        while True:
            await asyncio.sleep(self.settings.ohip_ping_interval_seconds)
            await websocket.send(json.dumps({"type": "ping"}))

    @staticmethod
    def _extract_payloads(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data") or {}
        candidates = data.get("newEvent")
        if isinstance(candidates, dict):
            return [candidates]
        candidates = data.get("businessEvents")
        if candidates is None:
            candidates = payload
        if isinstance(candidates, list):
            return [item for item in candidates if isinstance(item, dict)]
        if isinstance(candidates, dict):
            parsed = parse_ohip_event(candidates)
            return [parsed.payload]
        return []
