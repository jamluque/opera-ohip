from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RetryDecision(StrEnum):
    SUCCESS = "success"
    RETRY = "retry"
    POISON = "poison"
    DELETED = "deleted"


@dataclass(frozen=True)
class RetryClassification:
    decision: RetryDecision
    reason: str
    retry_after_seconds: int | None = None


class RetryClassifier:
    def classify_http(self, status_code: int, *, is_delete_or_cancel: bool) -> RetryClassification:
        if status_code == 404 and is_delete_or_cancel:
            return RetryClassification(RetryDecision.DELETED, "resource deleted or cancelled")
        if status_code == 429:
            return RetryClassification(RetryDecision.RETRY, "rate limited")
        if 500 <= status_code <= 599:
            return RetryClassification(RetryDecision.RETRY, "server error")
        if status_code in {400, 404}:
            return RetryClassification(RetryDecision.POISON, "non-retryable OHIP error")
        if status_code == 401:
            return RetryClassification(RetryDecision.RETRY, "unauthorized after token refresh")
        return RetryClassification(RetryDecision.POISON, "unexpected OHIP error")
