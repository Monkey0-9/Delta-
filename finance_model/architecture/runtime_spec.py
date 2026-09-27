from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import FrozenSet


class RuntimeBackend(StrEnum):
    TRANSFORMERS = "transformers"
    VLLM = "vllm"
    TORCH = "torch"


class Precision(StrEnum):
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    model_id: str
    model_revision: str | None = None

    backend: RuntimeBackend = RuntimeBackend.TRANSFORMERS
    precision: Precision = Precision.BF16

    max_sequence_length: int = 2048
    max_new_tokens: int = 512

    temperature: float = 0.0
    top_p: float = 1.0

    device: str = "auto"

    trust_remote_code: bool = False

    required_capabilities: FrozenSet[str] = field(
        default_factory=frozenset
    )

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id cannot be empty")

        if self.max_sequence_length <= 0:
            raise ValueError("max_sequence_length must be > 0")

        if self.max_new_tokens <= 0:
            raise ValueError("max_new_tokens must be > 0")

        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be in [0, 2]")

        if not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be in (0, 1]")