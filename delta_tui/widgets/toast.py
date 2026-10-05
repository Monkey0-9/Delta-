"""Group 05 — Notification/toast manager (breach, fill, experiment done)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Toast:
    level: str  # info | warn | breach
    text: str
    at: str = ""


class ToastManager:
    def __init__(self, cap: int = 50) -> None:
        self._items: list[Toast] = []
        self.cap = cap

    def push(self, level: str, text: str) -> Toast:
        t = Toast(level, text, datetime.now(timezone.utc).isoformat())
        self._items.append(t)
        del self._items[: max(0, len(self._items) - self.cap)]
        return t

    def breach(self, text: str) -> Toast:
        return self.push("breach", text)

    def fill(self, text: str) -> Toast:
        return self.push("info", text)

    def experiment_done(self, text: str) -> Toast:
        return self.push("info", text)

    def items(self) -> list[Toast]:
        return list(self._items)
