"""
Iterative research loop for DELTA OS research automation.

Refines a hypothesis dict over a fixed number of iterations using a
registered ``backtest`` tool. Fail-closed by default (strict=True):
without a working backtest tool the loop returns DATA_UNAVAILABLE and
scores nothing. Synthetic hash scoring exists ONLY for offline unit
tests / simulator development / demos, is labeled
truth_status=SYNTHETIC, and is NEVER certification-eligible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib
import json


# Statuses returned in result["status"].
STATUS_SCORED = "SCORED"  # real backtest scores produced
STATUS_DATA_UNAVAILABLE = "DATA_UNAVAILABLE"  # no usable backtest; nothing scored
STATUS_SYNTHETIC_DEMO = "SYNTHETIC_DEMO"  # explicit demo/test scoring only


@dataclass
class ProvenanceEntry:
    """
    Single-iteration provenance record.

    Attributes:
        iteration: Zero-based iteration index
        hypothesis: Hypothesis snapshot for this iteration
        score: Objective score achieved
        tool_used: Tool name used for scoring
        timestamp: UTC timestamp of the iteration
        detail: Extra scoring detail
    """
    iteration: int
    hypothesis: Dict[str, Any]
    score: float
    tool_used: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detail: Dict[str, Any] = field(default_factory=dict)


def _synthetic_score(hypothesis: Dict[str, Any], iteration: int) -> float:
    """Deterministic offline score in [0, 1) from hypothesis content."""
    payload = json.dumps(hypothesis, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{payload}|{iteration}".encode()).hexdigest()
    return (int(digest[:8], 16) % 10000) / 10000.0


def _extract_score(result: Any, fallback: float) -> tuple[float, Dict[str, Any]]:
    """Extract a float score from a backtest tool result."""
    if isinstance(result, (int, float)):
        return float(result), {"raw": result}
    if isinstance(result, dict):
        for key in ("score", "sharpe_ratio", "sharpe", "metric", "pnl"):
            value = result.get(key)
            if isinstance(value, (int, float)):
                return float(value), {"raw": result, "key": key}
        return fallback, {"raw": result, "note": "no numeric field"}
    return fallback, {"raw": str(result)}


class ResearchLoop:
    """
    Simple iterative hypothesis-refinement loop.

    Features:
    - Uses registered ``backtest`` tool when available
    - Deterministic synthetic scoring otherwise
    - Per-iteration provenance entries
    - Best-hypothesis tracking
    """

    def __init__(
        self,
        registry: Any,
        permissions: Any = None,
        role: str = "researcher",
        backtest_tool: str = "backtest",
        strict: bool = True,
        allow_synthetic: bool = False,
        min_iter: int = 2,
        patience: int = 2,
        tol: float = 1e-6,
    ) -> None:
        """
        Initialize research loop.

        Args:
            registry: ToolRegistry-compatible object with
                list_tools()/invoke()/get().
            permissions: Optional PermissionManager-compatible object
                with check(role, tool).
            role: Role used for permission checks.
            backtest_tool: Registered tool name preferred for scoring.
            strict: Fail-closed flag. When True (default), a missing or
                exploding backtest tool yields STATUS_DATA_UNAVAILABLE
                with no scores — dead research can never pass as scored.
            allow_synthetic: Explicit opt-in for deterministic hash
                scoring in unit tests / simulator dev / demos ONLY.
                Result is labeled truth_status=SYNTHETIC and
                cert_eligible=False, and can never enter certification.
            min_iter: Minimum iterations before plateau counts as converged.
            patience: Consecutive iterations without improvement > tol
                required for converged=True.
            tol: Minimum best-score improvement counting as progress.
        """
        self._registry = registry
        self._permissions = permissions
        self._role = role
        self._backtest_tool = backtest_tool
        self._strict = strict
        self._allow_synthetic = allow_synthetic
        self._min_iter = max(2, int(min_iter))
        self._patience = max(1, int(patience))
        self._tol = float(tol)

    def _can_use_backtest(self) -> bool:
        """Check backtest tool availability and authorization."""
        try:
            tools = self._registry.list_tools()
        except AttributeError:
            return False
        if self._backtest_tool not in tools:
            return False
        if self._permissions is None:
            return True
        try:
            return bool(
                self._permissions.check(self._role, self._backtest_tool)
            )
        except (AttributeError, TypeError):
            return True

    def _refine(self, hypothesis: Dict[str, Any], score: float) -> Dict[str, Any]:
        """Produce next-iteration hypothesis from current score."""
        refined = dict(hypothesis)
        params = dict(refined.get("params", {}))
        params["iteration_score"] = round(float(score), 6)
        # Nudge a numeric threshold toward exploitation on good scores.
        threshold = params.get("threshold", 0.5)
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            threshold = 0.5
        step = 0.05 if score >= 0.5 else -0.05
        params["threshold"] = round(max(0.0, min(1.0, threshold + step)), 6)
        refined["params"] = params
        return refined

    def run(self, hypothesis: Dict[str, Any], max_iter: int = 3) -> Dict[str, Any]:
        """
        Run iterative refinement loop.

        Returns a result dict with status SCORED, DATA_UNAVAILABLE, or
        SYNTHETIC_DEMO; converged=True only when the plateau criterion
        (no improvement > tol for `patience` iterations after `min_iter`
        iterations) is met — never merely because the loop ran.
        """
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis must be a dict")
        max_iter = max(1, int(max_iter))

        if not self._can_use_backtest():
            if self._strict and not self._allow_synthetic:
                return {
                    "hypothesis": dict(hypothesis),
                    "status": STATUS_DATA_UNAVAILABLE,
                    "best_hypothesis": {},
                    "best_score": None,
                    "iterations": [],
                    "provenance": [],
                    "max_iter": max_iter,
                    "converged": False,
                    "converge_reason": "no_usable_backtest",
                    "synthetic_used": False,
                    "truth_status": "UNAVAILABLE",
                    "cert_eligible": False,
                    "strict": self._strict,
                }
            return self._run_synthetic(dict(hypothesis), max_iter)

        current = dict(hypothesis)
        provenance: List[ProvenanceEntry] = []
        history: List[Dict[str, Any]] = []
        best_score: Optional[float] = None
        best_hypothesis: Optional[Dict[str, Any]] = None
        stagnant = 0
        any_synthetic = False

        for i in range(max_iter):
            try:
                raw = self._registry.invoke(
                    self._backtest_tool,
                    hypothesis=dict(current),
                    iteration=i,
                )
            except Exception as exc:  # noqa: BLE001 - fail closed
                if self._strict:
                    raise
                if not self._allow_synthetic:
                    return {
                        "hypothesis": dict(hypothesis),
                        "status": STATUS_DATA_UNAVAILABLE,
                        "best_hypothesis": best_hypothesis or {},
                        "best_score": best_score,
                        "iterations": history,
                        "provenance": [entry.__dict__ for entry in provenance],
                        "max_iter": max_iter,
                        "converged": False,
                        "converge_reason": f"backtest_failed: {exc}",
                        "synthetic_used": False,
                        "truth_status": "UNAVAILABLE",
                        "cert_eligible": False,
                        "strict": self._strict,
                    }
                score = _synthetic_score(current, i)
                detail = {"fallback": True, "error": str(exc)}
                tool_used = "synthetic"
                any_synthetic = True
            else:
                score, detail = _extract_score(raw, float("nan"))
                if isinstance(score, float) and score != score:  # NaN: no numeric field
                    return {
                        "hypothesis": dict(hypothesis),
                        "status": STATUS_DATA_UNAVAILABLE,
                        "best_hypothesis": best_hypothesis or {},
                        "best_score": best_score,
                        "iterations": history,
                        "provenance": [entry.__dict__ for entry in provenance],
                        "max_iter": max_iter,
                        "converged": False,
                        "converge_reason": "backtest_returned_no_score",
                        "synthetic_used": False,
                        "truth_status": "UNAVAILABLE",
                        "cert_eligible": False,
                        "strict": self._strict,
                    }
                tool_used = self._backtest_tool

            score = float(score)
            improved = best_score is None or (score - best_score) > self._tol
            stagnant = 0 if improved else stagnant + 1
            entry = ProvenanceEntry(
                iteration=i,
                hypothesis=dict(current),
                score=score,
                tool_used=tool_used,
                detail=detail,
            )
            provenance.append(entry)
            history.append(
                {
                    "iteration": i,
                    "hypothesis": dict(current),
                    "score": score,
                    "tool_used": tool_used,
                }
            )
            if improved:
                best_score = score
                best_hypothesis = dict(current)
            current = self._refine(current, score)
            if len(history) >= self._min_iter and stagnant >= self._patience:
                return self._finish(
                    dict(hypothesis), history, provenance,
                    best_hypothesis or {}, best_score,
                    max_iter, True, "plateau", any_synthetic,
                    "SYNTHETIC" if any_synthetic else "REAL",
                )

        return self._finish(
            dict(hypothesis), history, provenance,
            best_hypothesis or {}, best_score,
            max_iter, False, "max_iter_exhausted", any_synthetic,
            "SYNTHETIC" if any_synthetic else "REAL",
        )

    def _finish(self, hypothesis: Dict[str, Any], history: List[Dict[str, Any]],
                provenance: List[ProvenanceEntry], best_h: Dict[str, Any],
                best_s: Optional[float], max_iter: int, converged: bool,
                reason: str, synthetic: bool, truth: str) -> Dict[str, Any]:
        return {
            "hypothesis": hypothesis,
            "status": STATUS_SYNTHETIC_DEMO if synthetic else STATUS_SCORED,
            "best_hypothesis": best_h,
            "best_score": best_s,
            "iterations": history,
            "provenance": [entry.__dict__ for entry in provenance],
            "max_iter": max_iter,
            "converged": converged,
            "converge_reason": reason,
            "synthetic_used": synthetic,
            "truth_status": ("SYNTHETIC" if synthetic else truth),
            "cert_eligible": (not synthetic) and converged,
            "strict": self._strict,
        }

    def _run_synthetic(self, hypothesis: Dict[str, Any], max_iter: int) -> Dict[str, Any]:
        """Explicit demo/test scoring. Labeled, never certifiable."""
        current = dict(hypothesis)
        provenance: List[ProvenanceEntry] = []
        history: List[Dict[str, Any]] = []
        best_score: Optional[float] = None
        best_hypothesis: Optional[Dict[str, Any]] = None
        stagnant = 0
        for i in range(max_iter):
            score = _synthetic_score(current, i)
            improved = best_score is None or (score - best_score) > self._tol
            stagnant = 0 if improved else stagnant + 1
            provenance.append(ProvenanceEntry(
                iteration=i, hypothesis=dict(current), score=score,
                tool_used="synthetic", detail={"demo": True}))
            history.append({"iteration": i, "hypothesis": dict(current),
                            "score": score, "tool_used": "synthetic"})
            if improved:
                best_score = score
                best_hypothesis = dict(current)
            current = self._refine(current, score)
            if len(history) >= self._min_iter and stagnant >= self._patience:
                return self._finish(hypothesis, history, provenance,
                                    best_hypothesis or {}, best_score,
                                    max_iter, True, "plateau", True, "SYNTHETIC")
        return self._finish(hypothesis, history, provenance,
                            best_hypothesis or {}, best_score,
                            max_iter, False, "max_iter_exhausted", True, "SYNTHETIC")


__all__ = [
    "ProvenanceEntry",
    "ResearchLoop",
]
