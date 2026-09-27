"""Alert engine: threshold rules over metric snapshots -> fired alerts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AlertRule:
    name: str
    metric: str
    op: str  # "gt" | "lt"
    threshold: float
    severity: str = "warning"

    def __post_init__(self) -> None:
        if self.op not in ("gt", "lt"):
            raise ValueError("op must be gt|lt.")
        if not self.name.strip() or not self.metric.strip():
            raise ValueError("name and metric required.")


@dataclass(frozen=True, slots=True)
class Alert:
    rule: str
    metric: str
    value: float
    severity: str


class AlertEngine:
    def __init__(self, rules: tuple[AlertRule, ...] = ()) -> None:
        self._rules = rules
        self._active: set[str] = set()

    def evaluate(self, metrics: dict[str, float]) -> list[Alert]:
        fired: list[Alert] = []
        for rule in self._rules:
            if rule.metric not in metrics:
                continue
            value = metrics[rule.metric]
            hit = value > rule.threshold if rule.op == "gt" else value < rule.threshold
            if hit:
                fired.append(Alert(rule.name, rule.metric, value, rule.severity))
                self._active.add(rule.name)
            else:
                self._active.discard(rule.name)
        return fired

    @property
    def active(self) -> tuple[str, ...]:
        return tuple(sorted(self._active))
