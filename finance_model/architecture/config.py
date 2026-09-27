from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelConfig:
    model_id: str
    revision: str = "main"

    max_context_tokens: int = 32_768
    max_generation_tokens: int = 4_096

    temperature: float = 0.2
    top_p: float = 0.95

    trust_remote_code: bool = False

    finance_native: bool = True
    tool_use: bool = True
    structured_output: bool = True
    evidence_grounding: bool = True
    uncertainty_output: bool = True
    abstention: bool = True

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id cannot be empty")

        if self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive")

        if self.max_generation_tokens <= 0:
            raise ValueError("max_generation_tokens must be positive")

        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature outside valid range")

        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be in (0, 1]")