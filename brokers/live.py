"""Live-trading gateway: fail-closed by design.

There is NO real-venue adapter in this repository (no FIX initiator to a
broker, no exchange membership, no clearing). This gateway therefore REFUSES
live execution unless ALL of the following hold, and even then routes ONLY to
explicitly configured paper/test venues:

  1. DELTA_LIVE=ARMED environment opt-in, AND
  2. a signed authorization record (approver + reason + expiry), AND
  3. target venue explicitly allow-listed as non-production, AND
  4. global kill switch NOT active.

Anything else raises LiveBlocked naming every missing requirement. This is
the honest implementation of "live trading readiness": the code proves it
cannot trade live by accident, and documents exactly what would be required.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

LIVE_VERSION = "live-gw-v1"
PAPER_VENUES = frozenset({"DELTA-PAPER", "TEST-VENUE"})


class LiveBlocked(Exception):
    pass


@dataclass(frozen=True, slots=True)
class LiveAuthorization:
    approver: str
    reason: str
    venue: str
    expires_at: str  # ISO UTC; must be future

    def valid(self, now_s: float | None = None) -> tuple[bool, str]:
        if not self.approver.strip():
            return False, "missing approver"
        if not self.reason.strip():
            return False, "missing reason"
        if self.venue not in PAPER_VENUES:
            return False, f"venue {self.venue} is not an allow-listed test venue"
        try:
            exp = datetime.fromisoformat(self.expires_at)
            now = datetime.now(timezone.utc)
            if exp.tzinfo is None:
                return False, "expires_at must be timezone-aware"
            if exp <= now:
                return False, "authorization expired"
        except (ValueError, TypeError):
            return False, "unparseable expires_at"
        return True, "ok"


def _requirements(auth: LiveAuthorization | None, kill_active: bool) -> list[str]:
    missing = []
    if os.environ.get("DELTA_LIVE", "").upper() != "ARMED":
        missing.append("DELTA_LIVE=ARMED not set")
    if auth is None:
        missing.append("no LiveAuthorization record")
    else:
        ok, why = auth.valid()
        if not ok:
            missing.append(f"invalid authorization: {why}")
    if kill_active:
        missing.append("global kill switch is ACTIVE")
    return missing


def submit_live(order: dict, auth: LiveAuthorization | None = None,
                kill_active: bool = True, venue: str = "DELTA-PAPER"):
    """Entry point for any live order. Fail-closed. Returns venue receipt."""
    if venue not in PAPER_VENUES:
        raise LiveBlocked(
            f"venue {venue} has no adapter in this repository (no broker FIX "
            "initiator, no membership, no clearing). Live trading there is "
            "not implemented — this is a refusal, not a limitation to bypass.")
    missing = _requirements(auth, kill_active)
    if missing:
        raise LiveBlocked("live execution refused: " + "; ".join(missing))
    if not order.get("symbol") or float(order.get("quantity", 0)) <= 0:
        raise LiveBlocked("invalid order (symbol/quantity required).")
    return {"status": "ROUTED-TO-TEST-VENUE", "venue": venue,
            "order": dict(order), "gw": LIVE_VERSION,
            "warning": "NOT a live market execution"}


__all__ = ["LIVE_VERSION", "PAPER_VENUES", "LiveBlocked", "LiveAuthorization",
           "submit_live"]
