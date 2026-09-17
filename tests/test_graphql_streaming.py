from types import SimpleNamespace

from pydantic import SecretStr

from ohip_bridge.graphql import OhipStreamingClient


def settings():
    return SimpleNamespace(
        ohip_application_key=SecretStr("app-key"),
        ohip_streaming_ws_url="wss://ohip.example.com/subscriptions",
        ohip_chain_code="CHAIN",
        ohip_hotel_ids=["MAD01"],
        ohip_external_system_code="AWS_BYOD",
        ohip_subscription_query_file=None,
    )


def test_default_subscription_uses_new_event_and_saved_offset() -> None:
    client = OhipStreamingClient(settings(), oauth=None)  # type: ignore[arg-type]

    query = client._subscription_query({"offset": "97863"})

    assert "newEvent(input:" in query
    assert 'chainCode: "CHAIN"' in query
    assert 'offset: "97863"' in query
    assert "metadata { offset uniqueEventId }" in query
    assert "primaryKey" in query


def test_connection_init_carries_oracle_auth_payload() -> None:
    client = OhipStreamingClient(settings(), oauth=None)  # type: ignore[arg-type]

    assert client._connection_init_payload("token-1") == {
        "type": "connection_init",
        "payload": {"Authorization": "Bearer token-1", "x-app-key": "app-key"},
    }


def test_extract_payloads_reads_new_event() -> None:
    payload = {
        "data": {
            "newEvent": {
                "metadata": {"offset": "97863", "uniqueEventId": "evt-1"},
                "moduleName": "PROFILE",
                "eventName": "NEW PROFILE",
                "primaryKey": "123",
            }
        }
    }

    assert OhipStreamingClient._extract_payloads(payload) == [payload["data"]["newEvent"]]
