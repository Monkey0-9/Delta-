from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from core.domain.timestamp import ensure_utc, utc_now


@dataclass(slots=True)
class KillSwitch:
    """Independent kill switch: block live submission until re-armed by same actor."""

    active: bool = False
    activated_by: str = ""
    activated_at: datetime | None = None

    def activate(self, *, actor: str) -> None:
        self.active = True
        self.activated_by = actor
        self.activated_at = utc_now()

    def rearm(self, *, actor: str) -> None:
        if not self.active:
            return
        if actor != self.activated_by:
            raise PermissionError("only the activating actor may re-arm.")
        self.active = False
        self.activated_by = ""
        self.activated_at = None

    def check(self) -> None:
        if self.active:
            raise RuntimeError("kill switch active: all live submission blocked.")
