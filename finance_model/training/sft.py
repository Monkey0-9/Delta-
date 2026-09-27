from __future__ import annotations

import argparse

from datasets import load_dataset
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer


def train(
    model_name: str,
    dataset_path: str,
    output_dir: str,
    *,
    max_seq_length: int = 2048,
    epochs: float = 1.0,
    learning_rate: float = 2e-4,
    seed: int = 20260925,
) -> None:

    dataset = load_dataset(
        "json",
        data_files=dataset_path,
        split="train",
    )

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
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

    training_args = SFTConfig(
        output_dir=output_dir,

        num_train_epochs=epochs,

        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,

        learning_rate=learning_rate,

        warmup_ratio=0.05,

        logging_steps=10,
        save_steps=250,

        bf16=True,

        gradient_checkpointing=True,

        max_length=max_seq_length,

        report_to="none",

        seed=seed,

        remove_unused_columns=False,
    )

    trainer = SFTTrainer(
        model=model_name,
        args=training_args,
        train_dataset=dataset,
        peft_config=peft_config,
    )

    trainer.train()

    trainer.save_model(output_dir)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="DELTA Finance Model SFT/QLoRA training"
    )

    parser.add_argument(
        "--model",
        required=True,
    )

    parser.add_argument(
        "--dataset",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--max-length",
        type=int,
        default=2048,
    )

    parser.add_argument(
        "--epochs",
        type=float,
        default=1.0,
    )

    parser.add_argument(
        "--learning-rate",
        type=float,
        default=2e-4,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=20260925,
    )

    args = parser.parse_args()

    train(
        model_name=args.model,
        dataset_path=args.dataset,
        output_dir=args.output,
        max_seq_length=args.max_length,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()