from __future__ import annotations

from pathlib import Path

from datasets import Dataset

from finance_model.training.qlora import train_sft


MODEL_NAME = "Qwen/Qwen3-0.6B-Base"

OUTPUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "artifacts"
    / "finance_model"
    / "smoke"
)


def build_smoke_dataset() -> Dataset:
    examples = [
        {
            "text": (
                "DELTA financial analysis.\n"
                "Asset: AAPL\n"
                "Horizon: 1W\n"
                "Action: WAIT\n"
                "Confidence: 0.55\n"
                "Reason: insufficient verified evidence.\n"
            )
        },
        {
            "text": (
                "DELTA financial analysis.\n"
                "Asset: NVDA\n"
                "Horizon: 1M\n"
                "Action: HOLD\n"
                "Confidence: 0.61\n"
                "Reason: elevated volatility requires confirmation.\n"
            )
        },
        {
            "text": (
                "DELTA portfolio analysis.\n"
                "Risk: concentration\n"
                "Horizon: 1M\n"
                "Action: REDUCE\n"
                "Confidence: 0.72\n"
                "Reason: portfolio concentration exceeds the intended risk budget.\n"
            )
        },
        {
            "text": (
                "DELTA macro analysis.\n"
                "Event: Treasury yield shock\n"
                "Horizon: 1W\n"
                "Action: INVESTIGATE\n"
                "Confidence: 0.68\n"
                "Reason: regime conditions changed and additional evidence is required.\n"
            )
        },
        {
            "text": (
                "DELTA risk analysis.\n"
                "Condition: stale market data\n"
                "Action: NO_TRADE\n"
                "Confidence: 0.99\n"
                "Reason: trading must fail closed when required market data is stale.\n"
            )
        },
        {
            "text": (
                "DELTA decision analysis.\n"
                "Condition: model disagreement\n"
                "Action: WAIT\n"
                "Confidence: 0.64\n"
                "Reason: conflicting model outputs require additional analysis.\n"
            )
        },
    ]

    return Dataset.from_list(examples)


def main() -> None:
    dataset = build_smoke_dataset()

    print(f"Examples: {len(dataset)}")
    print(f"Model: {MODEL_NAME}")
    print(f"Output: {OUTPUT_DIR}")

    output = train_sft(
        MODEL_NAME,
        dataset,
        str(OUTPUT_DIR),
        num_train_epochs=1.0,
        learning_rate=2e-4,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=1,
        max_seq_length=256,
        use_qlora=True,
    )

    print("\nDELTA FM smoke training complete.")
    print(output)


if __name__ == "__main__":
    main()