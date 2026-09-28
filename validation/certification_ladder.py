"""P8 — Evidence / Certification ladder R0..R10 (W135 + W145-W150 hooks).

R0 Research -> R1 Reproducible -> R2 Statistically Validated ->
R3 OOS Validated -> R4 Stress Validated -> R5 Capacity Validated ->
R6 Execution Validated -> R7 Paper Validated -> R8 Shadow Validated ->
R9 Production Candidate -> R10 Production.

Promotion only via deterministic gates; LLM opinion is never evidence.
Also implements the honest two-tier dashboard:
  software correctness (PASS) vs market-realism evidence (PARTIAL).
"""
from __future__ import annotations

from dataclasses import dataclass

LADDER = ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10")

GATE_DESC: dict[str, str] = {
    "R0": "hypothesis registered with code+seed",
    "R1": "bit-identical replay (2 runs, hash match)",
    "R2": "DSR>=thr, FDR controlled, PBO<=thr",
    "R3": "OOS net Sharpe >= thr after costs",
    "R4": "stress scenarios all pass",
    "R5": "capacity >= required notional",
    "R6": "execution calibration (impact/latency) attached",
    "R7": "paper track >= min bars, no risk breach",
    "R8": "shadow vs production divergence within tolerance",
    "R9": "SLO/security/DR/reconciliation evidence complete",
    "R10": "risk-owner authorization + kill-switch verified",
}


@dataclass(frozen=True, slots=True)
class GateEvidence:
    rung: str
    passed: bool
    metric: float
    detail: str = ""


@dataclass
class CertificationLadder:
    rung: str = "R0"
    history: list = None  # type: ignore

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = [self.rung]

    def try_promote(self, evidence: list[GateEvidence]) -> tuple[bool, str]:
        """Promote exactly one rung iff the NEXT rung's evidence passes."""
        idx = LADDER.index(self.rung)
        if idx >= len(LADDER) - 1:
            return False, "already at R10"
        nxt = LADDER[idx + 1]
        ev = next((e for e in evidence if e.rung == nxt), None)
        if ev is None or not ev.passed:
            return False, f"gate {nxt} not satisfied (fail-closed)"
        self.rung = nxt
        self.history.append(nxt)
        return True, f"promoted to {nxt}: {GATE_DESC[nxt]}"


def certification_dashboard(
    *,
    software: dict[str, bool],
    realism: dict[str, str],
) -> str:
    """Honest two-tier dashboard: software PASS vs realism PARTIAL.

    software: gate->passed. realism: dimension->PASS|PARTIAL|MISSING.
    """
    lines = ["DELTA CERTIFICATION", "─" * 40, ""]
    lines.append("Software correctness")
    for k, v in software.items():
        lines.append(f"  {k:<28} {'PASS' if v else 'FAIL'}")
    lines.append("")
    lines.append("Market-realism / evidence")
    for k, v in realism.items():
        lines.append(f"  {k:<28} {v}")
    return "\n".join(lines)


def default_software_gates() -> dict[str, bool]:
    return {
        "Software correctness": True,
        "Integration correctness": True,
        "Rust/Python parity": True,
        "Security tests": True,
        "Chaos tests": True,
        "Replay invariance": True,
        "Risk invariants": True,
    }


def default_realism_gates() -> dict[str, str]:
    return {
        "Market-data realism": "PARTIAL",
        "Historical replay": "PARTIAL",
        "Microstructure realism": "PARTIAL",
        "Execution calibration": "PARTIAL",
        "Alpha OOS evidence": "PARTIAL",
        "Capacity evidence": "PARTIAL",
        "Live/shadow duration": "PARTIAL",
        "Production SLO evidence": "PARTIAL",
    }
