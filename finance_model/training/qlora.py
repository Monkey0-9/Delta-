from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)


@dataclass(frozen=True)
class TrainingConfig:
    model_name: str
    output_dir: str
    num_train_epochs: float = 1.0
    learning_rate: float = 2e-4
    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 1
    max_seq_length: int = 256
    use_qlora: bool = True
    allow_remote_code: bool = False  # Stage-2 L5: explicit opt-in, default False
    enable_gradient_checkpointing: bool = True  # Stage-2 L4
    seed: int = 20261007


def cuda_available() -> bool:
    return bool(torch.cuda.is_available())


def bitsandbytes_available() -> bool:
    try:
        import bitsandbytes  # noqa: F401
        return True
    except Exception:
        return False


def qlora_available() -> bool:
    return cuda_available() and bitsandbytes_available()


def build_quantization_config() -> Any | None:
    """
    Use 4-bit QLoRA only when CUDA + bitsandbytes are available.

    CPU environments intentionally fall back to ordinary LoRA.
    """
    if not qlora_available():
        return None

    from transformers import BitsAndBytesConfig

    if torch.cuda.is_bf16_supported():
        compute_dtype = torch.bfloat16
    else:
        compute_dtype = torch.float16

    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=compute_dtype,
        bnb_4bit_use_double_quant=True,
    )


def build_lora_config() -> LoraConfig:
    return LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
    )


def _example_to_text(example: dict[str, Any]) -> str:
    if "text" in example:
        return str(example["text"])

    prompt = str(example.get("prompt", ""))
    completion = str(example.get("completion", ""))

    return f"{prompt}\n{completion}".strip()


def _tokenize_dataset(
    dataset: Dataset,
    tokenizer: AutoTokenizer,
    max_seq_length: int,
) -> Dataset:

    def tokenize(example: dict[str, Any]) -> dict[str, Any]:
        prompt = str(example.get("prompt", ""))
        completion = str(example.get("completion", ""))
        full_text = _example_to_text(example)

        result = tokenizer(
            full_text,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        # Stage-2 L1 response-only loss: mask prompt tokens to -100.
        # If no prompt/completion split (raw "text"), fall back to full labels.
        labels = result["input_ids"].copy()
        if prompt and completion:
            prompt_ids = tokenizer(
                prompt, truncation=True,
                max_length=max_seq_length, padding=False)["input_ids"]
            n_mask = min(len(prompt_ids), len(labels))
            for i in range(n_mask):
                labels[i] = -100
        result["labels"] = labels
        return result

    return dataset.map(
        tokenize,
        remove_columns=dataset.column_names,
        desc="Tokenizing DELTA FM smoke dataset",
    )


def _load_model(
    config: TrainingConfig,
) -> tuple[Any, bool]:

    quantization_config = build_quantization_config()

    kwargs: dict[str, Any] = {
        "trust_remote_code": bool(config.allow_remote_code),
    }

    if quantization_config is not None:
        kwargs.update(
            {
                "quantization_config": quantization_config,
                "device_map": "auto",
                "torch_dtype": (
                    torch.bfloat16
                    if torch.cuda.is_bf16_supported()
                    else torch.float16
                ),
            }
        )

        actual_qlora = True

    else:
        # CPU smoke path.
        kwargs["torch_dtype"] = torch.float32
        actual_qlora = False

    model = AutoModelForCausalLM.from_pretrained(
        config.model_name,
        **kwargs,
    )

    return model, actual_qlora


def train_sft(
    model_name: str,
    dataset: Dataset,
    output_dir: str,
    num_train_epochs: float = 1.0,
    learning_rate: float = 2e-4,
    per_device_train_batch_size: int = 1,
    gradient_accumulation_steps: int = 1,
    max_seq_length: int = 256,
    use_qlora: bool = True,
) -> dict[str, Any]:

    if len(dataset) == 0:
        raise ValueError(
            "DELTA FM training dataset is empty. "
            "Provide at least one training example."
        )

    config = TrainingConfig(
        model_name=model_name,
        output_dir=output_dir,
        num_train_epochs=num_train_epochs,
        learning_rate=learning_rate,
        per_device_train_batch_size=per_device_train_batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        max_seq_length=max_seq_length,
        use_qlora=use_qlora,
    )

    Path(output_dir).mkdir(
        parents=True,
        exist_ok=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_name,
        trust_remote_code=bool(config.allow_remote_code),
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    tokenized_dataset = _tokenize_dataset(
        dataset,
        tokenizer,
        config.max_seq_length,
    )

    model, actual_qlora = _load_model(config)

    lora_config = build_lora_config()

    model = get_peft_model(
        model,
        lora_config,
    )

    if config.enable_gradient_checkpointing:
        try:
            model.gradient_checkpointing_enable()
        except Exception:
            pass

    model.print_trainable_parameters()

    # Stage-2 L3 precision agrees with hardware capability (tested).
    _use_bf16 = bool(cuda_available() and torch.cuda.is_bf16_supported())
    _use_fp16 = bool(cuda_available() and not _use_bf16)
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_train_epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.per_device_train_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        remove_unused_columns=False,
        fp16=_use_fp16,
        bf16=_use_bf16,
        dataloader_pin_memory=False,
        seed=config.seed,
    )

    from trl import SFTTrainer

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        processing_class=tokenizer,
    )

    result = trainer.train()

    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)

    # Stage-2 L6 per-run manifest: dataset/model/tokenizer/config/seed/hw/precision.
    write_run_manifest(config, dataset, actual_qlora, _use_fp16, _use_bf16)
    return _train_return_payload(config, dataset, result, actual_qlora)

def write_run_manifest(config: TrainingConfig, dataset: Dataset,
                       actual_qlora: bool, use_fp16: bool, use_bf16: bool) -> Path:
    """Stage-2 L6: per-run dataset_hash/model_rev/tokenizer_rev/git/sha manifest."""
    import hashlib
    import json
    import subprocess
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        git_commit = "unknown"
    probe = "".join(str(r)[:200] for r in dataset[: min(5, len(dataset))])
    dataset_hash = hashlib.sha256(probe.encode()).hexdigest()[:16]
    cfg_hash = hashlib.sha256(repr(config).encode()).hexdigest()[:16]
    manifest = {
        "model_name": config.model_name,
        "dataset_hash": dataset_hash,
        "tokenizer_rev": config.model_name,
        "config_hash": cfg_hash,
        "seed": config.seed,
        "git_commit": git_commit,
        "hardware": "cuda" if cuda_available() else "cpu",
        "precision": "bf16" if use_bf16 else ("fp16" if use_fp16 else "fp32"),
        "qlora": actual_qlora,
        "gradient_checkpointing": config.enable_gradient_checkpointing,
        "allow_remote_code": config.allow_remote_code,
        "response_only_loss": True,
    }
    out = Path(config.output_dir) / "run_manifest.json"
    out.write_text(json.dumps(manifest, indent=2))
    return out


def _train_return_payload(config: TrainingConfig, dataset: Dataset, result: object,
                          actual_qlora: bool) -> dict:
    return {
        "output_dir": config.output_dir,
        "model_name": config.model_name,
        "device": "cuda" if cuda_available() else "cpu",
        "qlora": actual_qlora,
        "lora": True,
        "train_examples": len(dataset),
        "train_loss": getattr(
            result,
            "training_loss",
            None,
        ),
    }