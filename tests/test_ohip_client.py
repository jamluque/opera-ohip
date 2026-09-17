from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr

from ohip_bridge.ohip_client import OHIPClient, OHIPHTTPError


class FakeTokenProvider:
    def __init__(self) -> None:
        self.invalidated = 0
        self.calls = 0

    async def token(self):
        self.calls += 1
        return SimpleNamespace(access_token=f"token-{self.calls}")

    def invalidate(self) -> None:
        self.invalidated += 1


def settings():
    return SimpleNamespace(
        ohip_gateway_url="https://ohip.example.com",
        ohip_application_key=SecretStr("app-key"),
        ohip_chain_code="CHAIN",
        ohip_enterprise_id="ENT",
    )


def test_headers_include_oracle_trace_headers() -> None:
    client = OHIPClient(settings(), FakeTokenProvider())

    headers = client._headers("token-1", "MAD01")

    assert headers["X-Originating-Application"] == "opera-ohip"
    assert UUID(headers["X-Request-Id"])


@pytest.mark.asyncio
async def test_401_invalidates_token_and_retries_once() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        if len(seen) == 1:
            return httpx.Response(401, json={"error": "expired"})
        return httpx.Response(200, json={"reservation": {"reservationId": "resv-1"}})

    provider = FakeTokenProvider()
    client = OHIPClient(
        settings(), provider, httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    response = await client.get_reservation("MAD01", "resv-1")

    assert response.payload["reservation"]["reservationId"] == "resv-1"
    assert provider.invalidated == 1
    assert seen == ["Bearer token-1", "Bearer token-2"]
    await client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 500, 503])
async def test_retryable_http_errors(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "7"} if status_code == 429 else {}
        return httpx.Response(status_code, text="retry later", headers=headers)

    client = OHIPClient(
        settings(), FakeTokenProvider(), httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(OHIPHTTPError) as exc:
        await client.get_profile("profile-1", "MAD01")

    assert exc.value.status_code == status_code
    if status_code == 429:
        assert exc.value.retry_after == 7
    await client.close()


@pytest.mark.asyncio
async def test_404_is_reported_to_service_for_delete_cancel_decision() -> None:
    client = OHIPClient(
        settings(),
        FakeTokenProvider(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(404))),
    )

    with pytest.raises(OHIPHTTPError) as exc:
        await client.get_folios("MAD01", "resv-missing")

    assert exc.value.status_code == 404
    await client.close()


class _Recorder:
    def __init__(self):
        self.calls = []

    async def request(self, method, url, headers=None, params=None):
        self.calls.append((method, url, params))
        return httpx.Response(200, json={"reservation": {}})


@pytest.mark.asyncio
async def test_get_reservation_sends_fetch_instructions():
    rec = _Recorder()
    client = OHIPClient(settings(), FakeTokenProvider(), http_client=rec)
    await client.get_reservation("MAD01", "resv-1")
    _, url, params = rec.calls[-1]
    assert url.endswith("/rsv/v1/hotels/MAD01/reservations/resv-1")
    assert params["fetchInstructions"] == ["Reservation"]


@pytest.mark.asyncio
async def test_get_folios_sends_fetch_instructions():
    rec = _Recorder()
    client = OHIPClient(settings(), FakeTokenProvider(), http_client=rec)
    await client.get_folios("MAD01", "resv-1")
    _, _, params = rec.calls[-1]
    assert params["fetchInstructions"] == [
        "Postings", "Totalbalance", "Transactioncodes", "Windowbalances",
    ]
