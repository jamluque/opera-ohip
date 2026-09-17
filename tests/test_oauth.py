import asyncio
import time
from types import SimpleNamespace

import pytest

from ohip_bridge.oauth import OAuthClient, OAuthToken


def settings():
    return SimpleNamespace(ohip_token_refresh_skew_seconds=120)


@pytest.mark.asyncio
async def test_token_refresh_is_single_flight(monkeypatch):
    client = OAuthClient(settings())
    calls = []

    async def fake_fetch():
        calls.append(1)
        await asyncio.sleep(0.01)
        return OAuthToken("tok", time.time() + 3600)

    monkeypatch.setattr(client, "_fetch_token", fake_fetch)
    await asyncio.gather(*(client.token() for _ in range(5)))
    assert len(calls) == 1
