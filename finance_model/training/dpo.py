from __future__ import annotations

import argparse

from datasets import load_dataset
from peft import LoraConfig
from trl import DPOConfig, DPOTrainer


def train(
    model_name: str,
    dataset_path: str,
    output_dir: str,
) -> None:
    dataset = load_dataset(
        "json",
        data_files=dataset_path,
        split="train",
    )

    peft_config = LoraConfig(
        r=64,
        lora_alpha=128,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
        ],
    )

    args = DPOConfig(
        output_dir=output_dir,
        num_train_epochs=1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=5e-6,
        bf16=True,
        max_length=8192,
        logging_steps=10,
        report_to="none",
        seed=42,
    )

    trainer = DPOTrainer(
        model=model_name,
        args=args,
        train_dataset=dataset,
        peft_config=peft_config,
    )

    trainer.train()
    trainer.save_model(output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    train(
        args.model,
        args.dataset,
        args.output,
    )