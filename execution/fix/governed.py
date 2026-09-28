"""W191-W200 governed FIX access: paper/shadow only (fail-closed).

Wraps execution.fix.session.FixSession (sequence discipline, gap detection).
Any live mode is rejected before a session can open so no order can escape
governance. Interface frozen so the future live adapter is a drop-in.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from execution.fix.session import FixSession

GOVERNED_MODES = ("paper", "shadow")


@dataclass(slots=True)
class GovernedSession:
    sender: str
    target: str
    mode: str = "paper"
    session: FixSession | None = None
    _heartbeats: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in GOVERNED_MODES:
            raise ValueError(f"FIX logon denied: non-governed mode {self.mode!r}.")
        self.session = FixSession(self.sender, self.target)

    def logon(self) -> bool:
        assert self.session is not None
        self.session.send_logon()
        return True

    def heartbeat(self) -> int:
        assert self.session is not None
        raw = self.session.send_heartbeat()
        self._heartbeats.append(raw)
        return self.session.out_seq - 1

    def send_new_order(self, fields: list[tuple[str, str]]) -> str:
        assert self.session is not None
        if self.mode not in GOVERNED_MODES:
            raise ValueError("order-entry denied outside paper/shadow.")
        return self.session.send([("35", "D"), *fields])
