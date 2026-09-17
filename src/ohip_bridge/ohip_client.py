from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx

from ohip_bridge import metrics
from ohip_bridge.config import Settings
from ohip_bridge.oauth import OAuthClient, OAuthToken

logger = logging.getLogger(__name__)


class OAuthTokenProvider:
    def __init__(self, settings: Settings) -> None:
        self.client = OAuthClient(settings)

    async def token(self) -> OAuthToken:
        return await self.client.token()

    def invalidate(self) -> None:
        self.client._token = None


@dataclass(frozen=True)
class OHIPResponse:
    operation_id: str
    resource_type: str
    resource_id: str
    payload: dict[str, Any]
    status_code: int


class OHIPHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class OHIPClient:
    def __init__(
        self,
        settings: Settings,
        token_provider: OAuthTokenProvider,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.token_provider = token_provider
        self.base_url = str(settings.ohip_gateway_url).rstrip("/")
        self.http = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )
        self._owns_client = http_client is None

    async def close(self) -> None:
        if self._owns_client:
            await self.http.aclose()

    async def get_reservation(self, hotel_id: str, reservation_id: str) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/rsv/v1/hotels/{hotel_id}/reservations/{reservation_id}", hotel_id,
            params={"fetchInstructions": ["Reservation"]},
        )
        return OHIPResponse("getReservation", "reservation", reservation_id, payload, 200)

    async def get_profile(self, profile_id: str, hotel_id: str | None = None) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/crm/v1/profiles/{profile_id}", hotel_id,
            params={"fetchInstructions": ["Profile", "Communication"]},
        )
        return OHIPResponse("getProfile", "profile", profile_id, payload, 200)

    async def get_folios(self, hotel_id: str, reservation_id: str) -> OHIPResponse:
        payload = await self._request(
            "GET", f"/csh/v1/hotels/{hotel_id}/reservations/{reservation_id}/folios", hotel_id,
            params={"fetchInstructions": [
                "Postings", "Totalbalance", "Transactioncodes", "Windowbalances",
            ]},
        )
        return OHIPResponse("getFolio", "folio", reservation_id, payload, 200)

    async def get_transaction_details(self, hotel_id: str, transaction_no: str) -> OHIPResponse:
        payload = await self._request(
            "GET",
            f"/csh/v1/hotels/{hotel_id}/transactionDetails",
            hotel_id,
            params={"transactionNo": transaction_no, "includeGenerates": "true"},
        )
        return OHIPResponse(
            "getFolioTransactionDetails", "folio_transaction", transaction_no, payload, 200
        )

    async def _request(
        self,
        method: str,
        path: str,
        hotel_id: str | None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(2):
            token = await self.token_provider.token()
            headers = self._headers(token.access_token, hotel_id)
            started = time.perf_counter()
            url = path if path.startswith("http") else f"{self.base_url}{path}"
            response = await self.http.request(method, url, headers=headers, params=params)
            metrics.ohip_api_calls.inc()
            metrics.ohip_latency_seconds.observe(time.perf_counter() - started)
            if response.status_code == 401 and attempt == 0:
                self.token_provider.invalidate()
                continue
            if response.status_code == 429:
                retry_after = self._retry_after(response.headers.get("Retry-After"))
                metrics.ohip_http_errors.labels(status_code="429").inc()
                await asyncio.sleep(min(retry_after or 1, 5))
                raise OHIPHTTPError(429, response.text, retry_after)
            if response.status_code >= 400:
                metrics.ohip_http_errors.labels(status_code=str(response.status_code)).inc()
                raise OHIPHTTPError(response.status_code, response.text)
            return response.json() if response.content else {}
        metrics.ohip_http_errors.labels(status_code="401").inc()
        raise OHIPHTTPError(401, "Unauthorized after token refresh")

    def _headers(self, access_token: str, hotel_id: str | None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "x-app-key": self.settings.ohip_application_key.get_secret_value(),
            "x-chaincode": self.settings.ohip_chain_code,
            "enterpriseId": self.settings.ohip_enterprise_id,
            "X-Request-Id": str(uuid4()),
            "X-Originating-Application": "opera-ohip",
            "Accept": "application/json",
        }
        if hotel_id:
            headers["x-hotelid"] = hotel_id
        return headers

    def _retry_after(self, value: str | None) -> int | None:
        if not value:
            return None
        try:
            return max(0, int(value))
        except ValueError:
            return None
