"""W117/model-lifecycle: statistical promotion gates on DeploymentRegistry.

Stages RESEARCH -> candidate -> shadow -> production -> deprecated.
("validated" maps to candidate with gates; "retired" maps to deprecated.)
Transitions REQUIRE evidence (no judgment calls in code path):

  research->candidate : research_statistics gate pass (|IC|>0.02, DSR>0.5,
                        PBO<0.6) + walk-forward gate pass.
  candidate->shadow   : paper evidence (event-backtest OOS net > 0) + approver.
  shadow->production  : shadow edge (paper net > benchmark net) + named approver.
  any->deprecated     : reason required. production->shadow demotion allowed.

No model jumps research->production: _ALLOWED in deployment.registry already
forbids it; this layer adds the EVIDENCE checks per edge. All decisions audit-
logged by the underlying registry.
"""
from __future__ import annotations

from dataclasses import dataclass

from deployment.registry import DeploymentRegistry

LIFE_VERSION = "life-v1"


@dataclass(frozen=True, slots=True)
class GateEvidence:
    stats_gate_pass: bool
    wf_gate_pass: bool
    paper_net: float = 0.0
    benchmark_net: float = 0.0
    approver: str = ""
    reason: str = ""


class LifecycleError(Exception):
    pass


class ModelLifecycle:
    def __init__(self, registry: DeploymentRegistry | None = None) -> None:
        self._reg = registry or DeploymentRegistry()

    def register(self, name: str, version: str, artifact_hash: str, actor: str):
        return self._reg.register(name, version, artifact_hash, actor)

    def stage_of(self, name: str, version: str) -> str:
        dep = self._reg._current.get(f"{name}@{version}")
        if dep is None:
            raise LifecycleError("unknown model version.")
        return dep.stage

    def promote(self, name: str, version: str, stage: str, ev: GateEvidence):
        cur = self.stage_of(name, version)
        if (cur, stage) == ("research", "candidate"):
            if not (ev.stats_gate_pass and ev.wf_gate_pass):
                raise LifecycleError(
                    "candidate requires stats gate + walk-forward gate PASS.")
        elif (cur, stage) == ("candidate", "shadow"):
            if not (ev.paper_net > 0 and ev.approver.strip()):
                raise LifecycleError(
                    "shadow requires paper_net > 0 + named approver.")
        elif (cur, stage) == ("shadow", "production"):
            if not (ev.paper_net > ev.benchmark_net and ev.approver.strip()):
                raise LifecycleError(
                    "production requires paper edge over benchmark + approver.")
        elif stage in ("deprecated",):
            if not ev.reason.strip():
                raise LifecycleError("deprecation requires a reason.")
        elif (cur, stage) == ("production", "shadow"):
            if not ev.reason.strip():
                raise LifecycleError("demotion requires a reason.")
        try:
            return self._reg.promote(name, version, stage,
                                     ev.approver or "system")
        except ValueError as exc:
            raise LifecycleError(str(exc)) from exc

    def history(self, name: str) -> list:
        return list(self._reg._history.get(name, []))


__all__ = ["LIFE_VERSION", "GateEvidence", "LifecycleError", "ModelLifecycle"]
