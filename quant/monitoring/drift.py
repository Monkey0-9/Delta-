"""Stage-4: drift monitor (central feature+prediction+regime PSI → Models screen + auto-demote).

Today only finance_model/datasets/drift.py PSI screening exists and
quality_gate explicitly skips drift. This facade centralizes it with
per-pipeline budgets and a demote signal the registry consumes.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    e = np.asarray(expected, float)
    a = np.asarray(actual, float)
    qs = np.quantile(e, np.linspace(0, 1, bins + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    eh, _ = np.histogram(e, bins=qs)
    ah, _ = np.histogram(a, bins=qs)
    ep = np.clip(eh / max(1, len(e)), 1e-4, 1.0)
    ap = np.clip(ah / max(1, len(a)), 1e-4, 1.0)
    return float(np.sum((ap - ep) * np.log(ap / ep)))


@dataclass(frozen=True, slots=True)
class DriftReport:
    stream: str  # feature|prediction|regime
    psi: float
    demote: bool
    reason: str = ""


def check_drift(stream: str, expected: np.ndarray, actual: np.ndarray,
                warn_at: float = 0.2, demote_at: float = 0.5) -> DriftReport:
    v = psi(expected, actual)
    if v >= demote_at:
        return DriftReport(stream, v, True, f"PSI {v:.3f} >= demote {demote_at}")
    if v >= warn_at:
        return DriftReport(stream, v, False, f"PSI {v:.3f} >= warn {warn_at}")
    return DriftReport(stream, v, False, "stable")


__all__ = ["psi", "DriftReport", "check_drift"]
