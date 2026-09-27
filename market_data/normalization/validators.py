from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    event_id: str = ""


def validate_quote_fields(q: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        if q.bid < 0 or q.ask < 0:
            issues.append(ValidationIssue("NEG_PRICE", "negative bid/ask"))
        if q.ask < q.bid:
            issues.append(ValidationIssue("CROSSED", "ask below bid"))
        if q.received_time < q.event_time:
            issues.append(ValidationIssue("TIME_TRAVEL", "received before event"))
    except AttributeError as exc:
        issues.append(ValidationIssue("MISSING_FIELD", str(exc)))
    return issues


def validate_trade_fields(t: Any) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    try:
        if t.price <= 0:
            issues.append(ValidationIssue("BAD_PRICE", "non-positive price"))
        if t.quantity <= 0:
            issues.append(ValidationIssue("BAD_QTY", "non-positive quantity"))
    except AttributeError as exc:
        issues.append(ValidationIssue("MISSING_FIELD", str(exc)))
    return issues


def detect_duplicate(event_ids: set[str], event_id: str) -> bool:
    return event_id in event_ids
