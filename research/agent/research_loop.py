"""
Iterative research loop for DELTA OS research automation.

Refines a hypothesis dict over a fixed number of iterations,
preferring a registered ``backtest`` tool and falling back to a
deterministic synthetic score. Every iteration records a
provenance entry. Offline only: numpy, no network/LLM calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import hashlib
import json


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
        strict: bool = False,
    ) -> None:
        """
        Initialize research loop.

        Args:
            registry: ToolRegistry-compatible object with
                list_tools()/invoke()/get().
            permissions: Optional PermissionManager-compatible object
                with check(role, tool). Denied backtest use falls back
                to synthetic scoring.
            role: Role used for permission checks.
            backtest_tool: Registered tool name preferred for scoring.
            strict: P0 fail-closed flag (2026-09-30). When True, a backtest
                tool exception propagates instead of silently falling back
                to ``synthetic`` scoring, so dead research can never pass
                as scored. Default False for backward compat; promotion
                pipelines must use strict=True.
        """
        self._registry = registry
        self._permissions = permissions
        self._role = role
        self._backtest_tool = backtest_tool
        self._strict = strict

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

        Args:
            hypothesis: Initial hypothesis payload
            max_iter: Number of refinement iterations

        Returns:
            Result dict with best score/hypothesis, iteration
            history, and provenance entries.
        """
        if not isinstance(hypothesis, dict):
            raise ValueError("hypothesis must be a dict")
        max_iter = max(1, int(max_iter))

        current = dict(hypothesis)
        provenance: List[ProvenanceEntry] = []
        history: List[Dict[str, Any]] = []
        best_score: Optional[float] = None
        best_hypothesis: Optional[Dict[str, Any]] = None

        for i in range(max_iter):
            if self._can_use_backtest():
                try:
                    raw = self._registry.invoke(
                        self._backtest_tool,
                        hypothesis=dict(current),
                        iteration=i,
                    )
                    score, detail = _extract_score(
                        raw, _synthetic_score(current, i)
                    )
                    tool_used = self._backtest_tool
                except Exception as exc:  # noqa: BLE001 - offline fallback
                    if self._strict:
                        raise
                    score = _synthetic_score(current, i)
                    detail = {"fallback": True, "error": str(exc)}
                    tool_used = "synthetic"
            else:
                score = _synthetic_score(current, i)
                detail = {"fallback": True}
                tool_used = "synthetic"

            score = float(score)
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
            if best_score is None or score > best_score:
                best_score = score
                best_hypothesis = dict(current)
            current = self._refine(current, score)

        return {
            "hypothesis": dict(hypothesis),
            "best_hypothesis": best_hypothesis or {},
            "best_score": float(best_score or 0.0),
            "iterations": history,
            "provenance": [entry.__dict__ for entry in provenance],
            "max_iter": max_iter,
            "converged": len(history) > 0,
            "synthetic_used": any(h["tool_used"] == "synthetic" for h in history),
            "strict": self._strict,
        }


__all__ = [
    "ProvenanceEntry",
    "ResearchLoop",
]
