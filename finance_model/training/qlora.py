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
        text = _example_to_text(example)

        result = tokenizer(
            text,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )

        result["labels"] = result["input_ids"].copy()
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
        "trust_remote_code": True,
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
        trust_remote_code=True,
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

    model.print_trainable_parameters()

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
        fp16=False,
        bf16=False,
        dataloader_pin_memory=False,
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