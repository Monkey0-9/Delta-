from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from .ablations import matrix, validate_matrix
from .baselines import run_baselines
from .provenance import (
    create_experiment_registry,
    write_provenance,
)
from .release import final_gates
from .statistics import metric_report
from .stress import stress_report

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "finalization"


def command_freeze() -> None:

    ARTIFACTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_provenance(
        ARTIFACTS / "provenance.json"
    )

    (ARTIFACTS / "experiment_registry.json").write_text(
        json.dumps(
            create_experiment_registry(),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(
        "W81/W82 freeze artifacts created."
    )


def command_baselines(
    price_file: str,
) -> None:

    prices = pd.read_csv(
        price_file
    )

    result = run_baselines(
        prices
    )

    output = (
        ARTIFACTS
        / "baseline_returns.csv"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        output,
        index_label="date",
    )

    print(
        f"W84 baseline output: {output}"
    )


def command_statistics(
    returns_file: str,
) -> None:

    df = pd.read_csv(
        returns_file
    )

    if "strategy" not in df.columns:
        raise ValueError(
            "returns file requires strategy column"
        )

    if "return" not in df.columns:
        raise ValueError(
            "returns file requires return column"
        )

    reports = []

    for strategy, group in df.groupby(
        "strategy"
    ):

        reports.append(
            metric_report(
                strategy,
                group["return"].tolist(),
            ).to_dict()
        )

    output = (
        ARTIFACTS
        / "statistics.json"
    )

    output.write_text(
        json.dumps(
            reports,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"W97 statistics: {output}"
    )


def command_stress(
    returns_file: str,
) -> None:

    df = pd.read_csv(
        returns_file
    )

    reports = {}

    for strategy, group in df.groupby(
        "strategy"
    ):

        reports[strategy] = stress_report(
            group["return"].to_numpy()
        )

    output = (
        ARTIFACTS
        / "stress.json"
    )

    output.write_text(
        json.dumps(
            reports,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"W98 stress report: {output}"
    )


def command_gates() -> None:

    gates = final_gates()

    for gate in gates:

        print(
            f"{gate.name:30} "
            f"{gate.status}"
        )


def command_ablations() -> None:

    validate_matrix()

    output = (
        ARTIFACTS
        / "ablation_matrix.json"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            matrix(),
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"W86-W91 matrix: {output}"
    )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "DELTA W81-W100 finalization."
        )
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser(
        "freeze"
    )

    baseline = sub.add_parser(
        "baselines"
    )

    baseline.add_argument(
        "--prices",
        required=True,
    )

    statistics = sub.add_parser(
        "statistics"
    )

    statistics.add_argument(
        "--returns",
        required=True,
    )

    stress = sub.add_parser(
        "stress"
    )

    stress.add_argument(
        "--returns",
        required=True,
    )

    sub.add_parser(
        "ablations"
    )

    sub.add_parser(
        "gates"
    )

    args = parser.parse_args()

    if args.command == "freeze":
        command_freeze()

    elif args.command == "baselines":
        command_baselines(
            args.prices
        )

    elif args.command == "statistics":
        command_statistics(
            args.returns
        )

    elif args.command == "stress":
        command_stress(
            args.returns
        )

    elif args.command == "ablations":
        command_ablations()

    elif args.command == "gates":
        command_gates()


if __name__ == "__main__":
    main()
