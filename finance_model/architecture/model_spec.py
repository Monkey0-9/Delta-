from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ModelCapability(StrEnum):
    FINANCE_REASONING = "finance_reasoning"
    QUANT_REASONING = "quant_reasoning"
    TOOL_USE = "tool_use"
    EVIDENCE_GROUNDING = "evidence_grounding"
    PORTFOLIO_REASONING = "portfolio_reasoning"
    RISK_REASONING = "risk_reasoning"
    MACRO_REASONING = "macro_reasoning"
    COUNTERFACTUAL = "counterfactual"
    UNCERTAINTY = "uncertainty"
    ABSTENTION = "abstention"
    FAILURE_ANALYSIS = "failure_analysis"


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    version: str

    base_model: str
    capabilities: tuple[ModelCapability, ...]

    training_stage: str

    dataset_manifest_hash: str
    code_commit: str

    model_revision: str = "main"
    dtype: str = "bf16"
    quantization: str = "none"
    device: str = "unknown"

    tokenizer_hash: str = ""
    adapter_hash: str = ""

    training_config_hash: str = ""
    runtime_hash: str = ""

    def supports(
        self,
        capability: ModelCapability,
    ) -> bool:
        return capability in self.capabilities

    def identity(self) -> str:
        return f"{self.name}:{self.version}"

    def artifact_identity(self) -> str:
        return (
            f"{self.name}:{self.version}:"
            f"{self.dataset_manifest_hash}:"
            f"{self.code_commit}"
        )