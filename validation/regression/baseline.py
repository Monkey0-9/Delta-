from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RegressionVerdict:
    suite: str
    failures: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.failures


def check_protected_failures(resolved: dict[str, bool]) -> RegressionVerdict:
    failures = tuple(k for k, ok in resolved.items() if not ok)
    return RegressionVerdict("protected-failures", failures)
