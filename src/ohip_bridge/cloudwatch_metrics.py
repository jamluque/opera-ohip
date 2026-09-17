from __future__ import annotations

import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MetricPoint:
    name: str
    value: float = 1
    unit: str = "Count"


class CloudWatchMetrics:
    def __init__(self, namespace: str, region: str) -> None:
        self.namespace = namespace
        self.client = boto3.client("cloudwatch", region_name=region)

    def put(self, *points: MetricPoint) -> None:
        if not points:
            return
        try:
            self.client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {"MetricName": point.name, "Value": point.value, "Unit": point.unit}
                    for point in points
                ],
            )
        except (BotoCoreError, ClientError):
            logger.exception("failed to publish CloudWatch metrics")
