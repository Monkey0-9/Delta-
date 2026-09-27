from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass(frozen=True, slots=True)
class TrainingRuntime:
    device: str
    bf16: bool
    fp16: bool
    gradient_checkpointing: bool

    @classmethod
    def detect(cls) -> "TrainingRuntime":
        if not torch.cuda.is_available():
            return cls(
                device="cpu",
                bf16=False,
                fp16=False,
                gradient_checkpointing=False,
            )

        bf16 = bool(torch.cuda.is_bf16_supported())

        return cls(
            device="cuda",
            bf16=bf16,
            fp16=not bf16,
            gradient_checkpointing=True,
        )