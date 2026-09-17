# OHIP Business Event Examples

Synthetic examples live in [examples/ohip-business-events](../examples/ohip-business-events). They model the `newEvent` shape consumed by this project:

- `metadata.offset`
- `metadata.uniqueEventId`
- `chainCode`
- `hotelId`
- `moduleName`
- `eventName`
- `primaryKey`
- `detail[]`

They are not hotel data and do not contain secrets.

## Covered Routes

| File | Route | Enrichment API |
|---|---|---|
| `reservation-new.json` | `Reservation/*` | `getReservation` |
| `reservation-update.json` | `Reservation/*` | `getReservation` |
| `reservation-cancel.json` | `Reservation/*` | `getReservation` or deleted marker on valid 404 cancel |
| `profile-new.json` | `Profile/*` | `getProfile` |
| `cashiering-folio.json` | `Cashiering/Folio` | `getFolio` |
| `cashiering-transaction.json` | `Cashiering/Transaction` | `getFolioTransactionDetails` |

## Publish One Example To LocalStack SQS

Start local dependencies and queues:

```bash
docker compose up -d postgres localstack
./scripts/init-local-aws.sh
```

Publish an example directly to the FIFO queue:

```bash
AWS_ACCESS_KEY_ID=test \
AWS_SECRET_ACCESS_KEY=test \
AWS_DEFAULT_REGION=eu-west-1 \
aws --endpoint-url http://localhost:4566 sqs send-message \
  --queue-url http://localhost:4566/000000000000/opera-ohip-dev-events.fifo \
  --message-body file://examples/ohip-business-events/reservation-new.json \
  --message-group-id opera-ohip-stream \
  --message-deduplication-id evt-reservation-new-100001
```

For another file, change both `--message-body` and `--message-deduplication-id`.

## Parser Check

```bash
PYTHONPATH=.python-packages:src python3 -m pytest tests/test_business_event_examples.py -q
```

This only proves that each example can be parsed, routed, and resolved to the identifier needed by the current enricher.
