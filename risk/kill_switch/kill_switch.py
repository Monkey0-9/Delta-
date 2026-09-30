from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

try:
    from core.domain.timestamp import ensure_utc, utc_now  # type: ignore
except ImportError:  # repo-root layout: `core.*` is top-level
    try:
        from delta.core.domain.timestamp import ensure_utc, utc_now  # type: ignore
    except ImportError:
        from datetime import datetime, timezone

        def utc_now() -> datetime:  # fallback: always tz-aware UTC
            return datetime.now(timezone.utc)

        def ensure_utc(value: datetime) -> datetime:
            if value.tzinfo is None:
                raise ValueError("Delta requires timezone-aware datetimes.")
            return value.astimezone(timezone.utc)


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


@dataclass(slots=True)
class KillSwitchBoard:
    """Triple-layer kill: global / strategy / broker. Fail-closed: ANY active blocks.

    P0 audit fix: a single KillSwitch instance is insufficient — a strategy
    runaway must not require a global halt, and a broker outage must block
    only that venue. The board owns three independent switches; re-arm
    still requires the original activating actor per layer.
    """

    glob: KillSwitch = None  # type: ignore[assignment]
    strategy: KillSwitch = None  # type: ignore[assignment]
    broker: KillSwitch = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.glob is None:
            object.__setattr__(self, "glob", KillSwitch())
        if self.strategy is None:
            object.__setattr__(self, "strategy", KillSwitch())
        if self.broker is None:
            object.__setattr__(self, "broker", KillSwitch())

    def check(self) -> None:
        for name in ("glob", "strategy", "broker"):
            try:
                getattr(self, name).check()
            except RuntimeError as exc:
                raise RuntimeError(f"kill switch active [{name}]: submission blocked.") from exc

    def any_active(self) -> bool:
        return self.glob.active or self.strategy.active or self.broker.active

    # Backward-compatible convenience: bare activate()/rearm() act on the
    # GLOBAL layer (full halt). Prefer explicit glob/strategy/broker handles.
    def activate(self, *, actor: str) -> None:
        self.glob.activate(actor=actor)

    def rearm(self, *, actor: str) -> None:
        self.glob.rearm(actor=actor)
