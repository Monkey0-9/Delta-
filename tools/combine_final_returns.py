from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Delta")

baseline_file = (
    ROOT
    / "artifacts"
    / "finalization"
    / "baseline_returns.csv"
)

delta_file = (
    ROOT
    / "artifacts"
    / "finalization"
    / "delta_static_returns.csv"
)

output_file = (
    ROOT
    / "artifacts"
    / "finalization"
    / "all_strategy_returns.csv"
)


baseline = pd.read_csv(
    baseline_file
)

baseline = baseline.rename(
    columns={
        baseline.columns[0]: "date"
    }
)

long_rows = []

for strategy in baseline.columns:

    if strategy == "date":
        continue

    subset = baseline[
        ["date", strategy]
    ].copy()

    subset = subset.rename(
        columns={
            strategy: "return"
        }
    )

    subset["strategy"] = strategy

    long_rows.append(
        subset[
            [
                "date",
                "strategy",
                "return",
            ]
        ]
    )


delta = pd.read_csv(
    delta_file
)

long_rows.append(
    delta[
        [
            "date",
            "strategy",
            "return",
        ]
    ]
)

combined = pd.concat(
    long_rows,
    ignore_index=True,
)

combined["date"] = pd.to_datetime(
    combined["date"],
    utc=True,
)

combined["return"] = pd.to_numeric(
    combined["return"],
    errors="raise",
)

combined = combined.sort_values(
    [
        "date",
        "strategy",
    ]
)

combined.to_csv(
    output_file,
    index=False,
)

print(output_file)
