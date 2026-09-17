# Oracle OHIP Validation Notes

Use this checklist before pointing the listener at a real OHIP environment.

## Developer Portal

- The environment must show `Streaming Enabled`.
- Event consumption must be requested and approved for the target environment.
- Keep only one active stream for each `applicationKey + gateway URL + chainCode`.
- If disconnected for more than 24 hours, reconnect with the last saved `offset`.
- OHIP retains replayable streaming events for 7 days.

## Postman / GraphiQL

- Use a separate Oracle application key for manual testing. Do not test Postman and this listener with the same application key at the same time.
- Never sync real `CLIENT_SECRET`, OAuth tokens, or app keys to a public Postman workspace or Git repository.
- The WebSocket URL must be `wss://<gateway>/subscriptions?key=<sha256-app-key>`.
- Send `connection_init` with:

```json
{
  "type": "connection_init",
  "payload": {
    "Authorization": "Bearer <access_token>",
    "x-app-key": "<application_key>"
  }
}
```

- Subscribe with `newEvent(input: { chainCode: "<CHAIN>" })` and include at least `metadata { offset uniqueEventId }`, `eventName`, and `primaryKey`.

## Local Verification

```bash
PYTHONPATH=.python-packages:src python3 -m pytest
PYTHONPATH=.python-packages:src python3 -m ruff check .
```

The local tests do not prove Oracle connectivity. A real UAT check must confirm `connection_ack`, event receipt, SQS publication, S3 offset persistence, and no repeated 4401/4403/4409/4504 closes.
