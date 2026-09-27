"""Deployment registry: versioned promotions with audit log + rollback."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

STAGES = ("research", "candidate", "shadow", "production", "deprecated")
_ALLOWED = {
    "research": ("candidate",),
    "candidate": ("shadow", "research"),
    "shadow": ("production", "candidate"),
    "production": ("deprecated", "shadow"),
    "deprecated": (),
}


@dataclass(frozen=True, slots=True)
class Deployment:
    name: str
    version: str
    artifact_hash: str
    stage: str
    approved_by: str
    timestamp: str


class DeploymentRegistry:
    def __init__(self) -> None:
        self._current: dict[str, Deployment] = {}
        self._history: dict[str, list[Deployment]] = {}
        self._log: list[dict] = []

    def _audit(self, action: str, name: str, version: str, stage: str, actor: str) -> None:
        payload = {"action": action, "name": name, "version": version,
                   "stage": stage, "actor": actor,
                   "ts": datetime.now(timezone.utc).isoformat(),
                   "prev": self._log[-1]["hash"] if self._log else "0" * 64}
        payload["hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self._log.append(payload)

    def register(self, name: str, version: str, artifact_hash: str, actor: str) -> Deployment:
        if not artifact_hash.strip():
            raise ValueError("artifact_hash required.")
        dep = Deployment(name, version, artifact_hash, "research", actor,
                         datetime.now(timezone.utc).isoformat())
        self._current[f"{name}@{version}"] = dep
        self._history.setdefault(name, []).append(dep)
        self._audit("register", name, version, "research", actor)
        return dep

    def promote(self, name: str, version: str, stage: str, actor: str) -> Deployment:
        key = f"{name}@{version}"
        if key not in self._current:
            raise ValueError("unknown deployment.")
        cur = self._current[key]
        if stage not in _ALLOWED.get(cur.stage, ()):
            raise ValueError(f"illegal transition {cur.stage} -> {stage}.")
        if stage == "production" and not actor.strip():
            raise ValueError("production promotion needs an approver.")
        nxt = Deployment(cur.name, cur.version, cur.artifact_hash, stage, actor,
                         datetime.now(timezone.utc).isoformat())
        self._current[key] = nxt
        self._history[name].append(nxt)
        self._audit("promote", name, version, stage, actor)
        return nxt

    def rollback(self, name: str, actor: str) -> Deployment:
        prods = [d for d in self._history.get(name, []) if d.stage == "production"]
        if len(prods) < 2:
            raise ValueError("nothing to roll back to.")
        current, prev = prods[-1], prods[-2]
        self._history[name].append(Deployment(
            current.name, current.version, current.artifact_hash, "deprecated",
            actor, datetime.now(timezone.utc).isoformat()))
        restored = Deployment(prev.name, prev.version, prev.artifact_hash, "production",
                              actor, datetime.now(timezone.utc).isoformat())
        self._history[name].append(restored)
        self._current[f"{name}@{prev.version}"] = restored
        self._audit("rollback", name, prev.version, "production", actor)
        return restored

    def production(self, name: str) -> Deployment | None:
        prods = [d for d in self._history.get(name, []) if d.stage == "production"]
        return prods[-1] if prods else None

    def verify_log(self) -> bool:
        prev = "0" * 64
        for entry in self._log:
            if entry["prev"] != prev:
                return False
            check = dict(entry)
            h = check.pop("hash")
            recomputed = hashlib.sha256(
                json.dumps(check, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            if recomputed != h:
                return False
            prev = h
        return True
