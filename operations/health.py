"""Operations health: component heartbeats, staleness, status rollup.

Components heartbeat(name); health() reports UP/STALE/DOWN per component plus
a global rollup (DOWN if any DOWN, DEGRADED if any STALE). Thresholds explicit.
Dead-letter box collects failed events for replay inspection. No auto-healing
claims: DOWN requires operator action via acknowledge().
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

OPS_VERSION = "ops-v1"


@dataclass
class Component:
    name: str
    stale_after_s: float = 60.0
    down_after_s: float = 300.0
    last_beat: float = 0.0
    acked_down: bool = False

    def state(self, now: float) -> str:
        age = now - self.last_beat
        if age > self.down_after_s:
            return "DOWN"
        if age > self.stale_after_s:
            return "STALE"
        return "UP"


class HealthMonitor:
    def __init__(self) -> None:
        self._comps: dict[str, Component] = {}
        self._dead_letters: list[dict] = []

    def register(self, name: str, stale_after_s: float = 60.0,
                 down_after_s: float = 300.0) -> None:
        if not name.strip():
            raise ValueError("component name required.")
        if name in self._comps:
            raise ValueError(f"duplicate component: {name}.")
        self._comps[name] = Component(name, stale_after_s, down_after_s,
                                      time.time())

    def heartbeat(self, name: str, now_s: float | None = None) -> None:
        if name not in self._comps:
            raise ValueError(f"unknown component: {name}.")
        self._comps[name].last_beat = now_s if now_s is not None else time.time()
        self._comps[name].acked_down = False

    def dead_letter(self, event: dict, reason: str) -> None:
        self._dead_letters.append({"t": datetime.now(timezone.utc).isoformat(),
                                   "reason": reason, "event": dict(event)})

    def acknowledge(self, name: str, actor: str) -> None:
        if name not in self._comps:
            raise ValueError(f"unknown component: {name}.")
        if not actor.strip():
            raise ValueError("acknowledge requires an actor.")
        self._comps[name].acked_down = True

    def health(self, now_s: float | None = None) -> dict:
        now = now_s if now_s is not None else time.time()
        states = {n: c.state(now) for n, c in self._comps.items()}
        for n, c in self._comps.items():
            if states[n] == "DOWN" and c.acked_down:
                states[n] = "DOWN_ACKED"
        rollup = "UP"
        if any(s == "DOWN" for s in states.values()):
            rollup = "DOWN"
        elif any(s in ("STALE", "DOWN_ACKED") for s in states.values()):
            rollup = "DEGRADED"
        return {"version": OPS_VERSION, "rollup": rollup, "components": states,
                "dead_letters": len(self._dead_letters)}


__all__ = ["OPS_VERSION", "Component", "HealthMonitor"]
