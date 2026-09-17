from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ohip_bridge import metrics
from ohip_bridge.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    expires_at: float

    def is_expiring(self, skew_seconds: int) -> bool:
        return time.time() >= self.expires_at - skew_seconds


class OAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: OAuthToken | None = None

    async def token(self) -> OAuthToken:
        if self._token and not self._token.is_expiring(
            self.settings.ohip_token_refresh_skew_seconds
        ):
            return self._token
        self._token = await self._fetch_token()
        return self._token

    async def _fetch_token(self) -> OAuthToken:
        client_id = self.settings.ohip_client_id.get_secret_value()
        client_secret = self.settings.ohip_client_secret.get_secret_value()
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        headers = {
            "Authorization": f"Basic {credentials}",
            "x-app-key": self.settings.ohip_application_key.get_secret_value(),
            "x-hotelid": self.settings.ohip_hotel_ids[0],
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "client_credentials",
            "scope": self.settings.ohip_scope,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                str(self.settings.ohip_token_url),
                headers=headers,
                data=data,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        expires_in = int(payload.get("expires_in", 3600))
        metrics.oauth_refreshes.inc()
        logger.info("refreshed OAuth token", extra={"expires_in": expires_in})
        return OAuthToken(
            access_token=payload["access_token"],
            expires_at=time.time() + expires_in,
        )
