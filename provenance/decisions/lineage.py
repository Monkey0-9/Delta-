from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionLineage:
    decision_id: str
    data_version: str
    world_state_version: str
    quant_state_version: str
    model_version: str

    evidence_ids: tuple[str, ...]

    risk_decision_id: str | None = None
    order_id: str | None = None
    fill_ids: tuple[str, ...] = ()
    outcome_id: str | None = None

    def reconstructable(self) -> bool:
        return bool(
            self.decision_id
            and self.data_version
            and self.world_state_version
            and self.quant_state_version
            and self.model_version
        )