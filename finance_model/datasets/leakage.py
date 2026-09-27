from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable


@dataclass(frozen=True, slots=True)
class LeakageViolation:
    record_id: str
    violation_type: str
    field: str
    decision_time: str
    offending_time: str
    message: str


@dataclass(frozen=True, slots=True)
class LeakageAudit:
    total_records: int
    valid_records: int
    violations: tuple[LeakageViolation, ...]

    @property
    def passed(self) -> bool:
        return not self.violations


def _parse_timestamp(value: str) -> datetime:
    value = value.strip()

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"

    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


class PointInTimeLeakageAuditor:
    """
    Strict point-in-time leakage auditor.

    A datum is usable for a decision only when its effective/publication
    timestamp is <= the decision timestamp.

    This is intentionally fail-closed.
    """

    def audit(
        self,
        records: Iterable[dict[str, object]],
    ) -> LeakageAudit:
        violations: list[LeakageViolation] = []
        total = 0

        for record in records:
            total += 1

            record_id = str(record.get("record_id", ""))

            if not record_id:
                violations.append(
                    LeakageViolation(
                        record_id="<missing>",
                        violation_type="schema",
                        field="record_id",
                        decision_time="",
                        offending_time="",
                        message="Missing record_id",
                    )
                )
                continue

            decision_raw = record.get("decision_time")

            if not isinstance(decision_raw, str):
                violations.append(
                    LeakageViolation(
                        record_id=record_id,
                        violation_type="schema",
                        field="decision_time",
                        decision_time="",
                        offending_time="",
                        message="decision_time must be an ISO timestamp",
                    )
                )
                continue

            try:
                decision_time = _parse_timestamp(decision_raw)
            except ValueError:
                violations.append(
                    LeakageViolation(
                        record_id=record_id,
                        violation_type="schema",
                        field="decision_time",
                        decision_time=decision_raw,
                        offending_time="",
                        message="Invalid decision_time",
                    )
                )
                continue

            temporal_fields = (
                "published_at",
                "effective_at",
                "available_at",
            )

            for field in temporal_fields:
                raw = record.get(field)

                if raw is None:
                    continue

                if not isinstance(raw, str):
                    violations.append(
                        LeakageViolation(
                            record_id=record_id,
                            violation_type="schema",
                            field=field,
                            decision_time=decision_raw,
                            offending_time="",
                            message=f"{field} must be an ISO timestamp",
                        )
                    )
                    continue

                try:
                    event_time = _parse_timestamp(raw)
                except ValueError:
                    violations.append(
                        LeakageViolation(
                            record_id=record_id,
                            violation_type="schema",
                            field=field,
                            decision_time=decision_raw,
                            offending_time=raw,
                            message=f"Invalid {field}",
                        )
                    )
                    continue

                if event_time > decision_time:
                    violations.append(
                        LeakageViolation(
                            record_id=record_id,
                            violation_type="lookahead",
                            field=field,
                            decision_time=decision_raw,
                            offending_time=raw,
                            message=(
                                f"{field} occurs after decision_time"
                            ),
                        )
                    )

        return LeakageAudit(
            total_records=total,
            valid_records=total - len(violations),
            violations=tuple(violations),
        )