from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    model_id: str = "Qwen/Qwen3-0.6B-Base"

    output_dir: str = "artifacts/models/delta-fm-0.6b"

    max_seq_length: int = 2048

    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1

    gradient_accumulation_steps: int = 16

    learning_rate: float = 2e-4

    num_train_epochs: float = 2.0

    warmup_ratio: float = 0.05

    seed: int = 42

    bf16: bool = True
    gradient_checkpointing: bool = True

    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05

    def validate(self) -> None:
        if self.max_seq_length <= 0:
            raise ValueError("max_seq_length must be positive")

        if self.lora_rank <= 0:
            raise ValueError("lora_rank must be positive")

        if self.gradient_accumulation_steps <= 0:
            raise ValueError(
                "gradient_accumulation_steps must be positive"
            )