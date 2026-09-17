# Oracle OHIP Streaming Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the project runtime with Oracle OHIP Streaming guidance while keeping the existing SQS/enrichment architecture.

**Architecture:** Keep the current listener -> SQS FIFO -> enricher flow. Change only the OHIP edge: GraphQL subscription shape, authentication message, replay offset handling, graceful complete, heartbeat cadence, and REST trace headers.

**Tech Stack:** Python 3.11+, `websockets`, `httpx`, `pytest`, `ruff`, AWS SQS/S3/Aurora.

## Global Constraints

- No new dependencies.
- Do not store or print OHIP secrets.
- Keep SQS FIFO buffering and database idempotency unchanged.
- Use Oracle Streaming `newEvent(input: ...)` payloads with `metadata.offset` and `metadata.uniqueEventId`.
- Use one active listener per `applicationKey + gateway URL + chainCode`.

---

### Task 1: Oracle Streaming Subscription

**Files:**
- Modify: `src/ohip_bridge/graphql.py`
- Test: `tests/test_graphql_streaming.py`

**Interfaces:**
- Consumes: `OhipStreamingClient(settings, oauth)`
- Produces: `_subscription_query(offset: dict[str, Any] | None = None) -> str`, `_connection_init_payload(access_token: str) -> dict[str, Any]`, `_complete_message(subscription_id: str) -> str`

- [ ] **Step 1: Write failing tests**

```python
def test_default_subscription_uses_new_event_and_saved_offset() -> None:
    client = OhipStreamingClient(settings(), oauth=None)  # type: ignore[arg-type]
    query = client._subscription_query({"offset": "97863"})
    assert "newEvent(input:" in query
    assert 'chainCode: "CHAIN"' in query
    assert 'offset: "97863"' in query
    assert "metadata { offset uniqueEventId }" in query
    assert "primaryKey" in query
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_graphql_streaming.py -q`
Expected: FAIL because `_subscription_query` does not accept offset and the default query uses `businessEvents`.

- [ ] **Step 3: Write minimal implementation**

Build the default query string from settings and optional offset. Keep custom query-file override unchanged.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_graphql_streaming.py -q`
Expected: PASS.

### Task 2: Connection Init, Complete, and Payload Extraction

**Files:**
- Modify: `src/ohip_bridge/graphql.py`
- Test: `tests/test_graphql_streaming.py`

**Interfaces:**
- Consumes: `_connection_init_payload(access_token: str)`
- Produces: auth payload with `Authorization` and `x-app-key`; `_extract_payloads()` returns `newEvent` dicts.

- [ ] **Step 1: Write failing tests**

```python
def test_connection_init_carries_oracle_auth_payload() -> None:
    client = OhipStreamingClient(settings(), oauth=None)  # type: ignore[arg-type]
    assert client._connection_init_payload("token-1") == {
        "type": "connection_init",
        "payload": {"Authorization": "Bearer token-1", "x-app-key": "app-key"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_graphql_streaming.py -q`
Expected: FAIL because helper is missing.

- [ ] **Step 3: Write minimal implementation**

Use the helper inside `events()`, extract `payload.data.newEvent`, and send `complete` with the same subscription id in `finally` when the socket is still open.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_graphql_streaming.py -q`
Expected: PASS.

### Task 3: REST Trace Headers

**Files:**
- Modify: `src/ohip_bridge/ohip_client.py`
- Test: `tests/test_ohip_client.py`

**Interfaces:**
- Consumes: `OHIPClient._headers(access_token: str, hotel_id: str | None)`
- Produces: `X-Request-Id` and `X-Originating-Application` headers.

- [ ] **Step 1: Write failing test**

```python
def test_headers_include_oracle_trace_headers() -> None:
    client = OHIPClient(settings(), FakeTokenProvider())
    headers = client._headers("token-1", "MAD01")
    assert headers["X-Originating-Application"] == "opera-ohip"
    assert UUID(headers["X-Request-Id"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_ohip_client.py -q`
Expected: FAIL because trace headers are absent.

- [ ] **Step 3: Write minimal implementation**

Generate one UUID per HTTP request header set using `uuid.uuid4()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest tests/test_ohip_client.py -q`
Expected: PASS.

### Task 4: Defaults and Operator Notes

**Files:**
- Modify: `src/ohip_bridge/config.py`
- Modify: `README.md`
- Create: `docs/oracle-ohip-validation.md`

**Interfaces:**
- Produces: `ohip_ping_interval_seconds` default `15`.

- [ ] **Step 1: Update default ping interval**

Set `ohip_ping_interval_seconds: int = 15`.

- [ ] **Step 2: Add concise validation notes**

Document Postman/Oracle validation, no secrets, one active stream, replay limits, and expected test commands.

- [ ] **Step 3: Verify**

Run: `PYTHONPATH=.python-packages:src python3 -m pytest`
Run: `PYTHONPATH=.python-packages:src python3 -m ruff check .`
Run: `graphify update .`
