#!/usr/bin/env bash
set -euo pipefail

export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-eu-west-1}"
ENDPOINT_URL="${ENDPOINT_URL:-http://localhost:4566}"

aws --endpoint-url "$ENDPOINT_URL" sqs create-queue \
  --queue-name opera-ohip-dev-events-dlq.fifo \
  --attributes FifoQueue=true,ContentBasedDeduplication=false

DLQ_URL="$ENDPOINT_URL/000000000000/opera-ohip-dev-events-dlq.fifo"
DLQ_ARN="$(aws --endpoint-url "$ENDPOINT_URL" sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)"

QUEUE_ATTRIBUTES="$(python3 - "$DLQ_ARN" <<'PY'
import json
import sys

print(json.dumps({
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "VisibilityTimeout": "120",
    "RedrivePolicy": json.dumps({
        "deadLetterTargetArn": sys.argv[1],
        "maxReceiveCount": "5",
    }),
}))
PY
)"

aws --endpoint-url "$ENDPOINT_URL" sqs create-queue \
  --queue-name opera-ohip-dev-events.fifo \
  --attributes "$QUEUE_ATTRIBUTES"

aws --endpoint-url "$ENDPOINT_URL" s3 mb "s3://opera-ohip-dev-raw"
