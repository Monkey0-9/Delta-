from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ProtectedFailureCase:
    failure_id: str
    description: str
    expected_action: str
    input_state: dict[str, Any]
    forbidden_actions: tuple[str, ...]

    def violates(self, action: str) -> bool:
        return action in self.forbidden_actions