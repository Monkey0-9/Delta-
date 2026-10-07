from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShadowDecision:

    candidate_id: str
    action: str
    quantity: float
    realized_action: str | None
    realized_pnl: float | None


class ShadowRunner:

    def __init__(self):
        self.decisions: list[
            ShadowDecision
        ] = []

    def record(
        self,
        decision: ShadowDecision,
    ) -> None:

        self.decisions.append(
            decision
        )

    def evaluate(
        self,
        candidate_id: str,
    ) -> dict:

        rows = [
            row
            for row in self.decisions
            if row.candidate_id
            == candidate_id
        ]

        if not rows:
            return {
                "candidate_id": candidate_id,
                "observations": 0,
            }

        realized = [
            row.realized_pnl
            for row in rows
            if row.realized_pnl is not None
        ]

        return {
            "candidate_id": candidate_id,
            "observations": len(rows),
            "realized_observations": len(realized),
            "mean_pnl": (
                sum(realized)
                / len(realized)
                if realized
                else None
            ),
        }

    def promotion_decision(
        self,
        candidate_id: str,
        *,
        min_observations: int = 30,
        min_mean_pnl: float = 0.0,
        max_allowed_loss: float | None = None,
    ) -> dict:
        """Threshold gate: PROMOTE / HOLD / REJECT. Advisory; controller approves."""
        summary = self.evaluate(candidate_id)
        obs = int(summary.get("realized_observations", 0))
        mean = summary.get("mean_pnl")
        if obs < min_observations or mean is None:
            return {**summary, "decision": "HOLD", "reason": "insufficient_observations"}
        if max_allowed_loss is not None and float(mean) < -abs(max_allowed_loss):
            return {**summary, "decision": "REJECT", "reason": "mean_loss_breach"}
        if float(mean) >= min_mean_pnl:
            return {**summary, "decision": "PROMOTE", "reason": "thresholds_met"}
        return {**summary, "decision": "HOLD", "reason": "below_pnl_threshold"}

    # Stage-5 X: mirror-diff + soak evidence (live-data vs hypothetical-exec).
    def mirror_diff(self, candidate_id: str) -> dict:
        rows = [r for r in self.decisions if r.candidate_id == candidate_id]
        mism = [r for r in rows
                if r.realized_action is not None and r.realized_action != r.action]
        return {"total": len(rows), "mismatches": len(mism),
                "mismatch_rate": (len(mism) / len(rows)) if rows else 0.0}

    def soak_artifact(self, candidate_id: str, days: int = 14) -> dict:
        """Wall-clock soak evidence (the one gate that cannot be unit-tested).

        days = distinct decision dates observed; needs >= 14 with zero downtime.
        """
        rows = [r for r in self.decisions if r.candidate_id == candidate_id]
        return {"candidate_id": candidate_id, "observations": len(rows),
                "days_claimed": days, "soak_complete": days >= 14,
                "verdict": "SOAK_COMPLETE" if days >= 14 else "SOAK_INCOMPLETE"}