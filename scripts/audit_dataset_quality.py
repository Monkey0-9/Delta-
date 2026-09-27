from __future__ import annotations

import argparse
import json

from finance_model.datasets.drift import (
    DistributionDriftDetector,
)
from finance_model.datasets.quality_gate import (
    DatasetQualityGate,
)


def load_jsonl(path: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            value = json.loads(line)

            if not isinstance(value, dict):
                raise ValueError(
                    f"Line {line_number} is not an object"
                )

            rows.append(value)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "reference",
    )

    parser.add_argument(
        "current",
    )

    args = parser.parse_args()

    reference = load_jsonl(args.reference)
    current = load_jsonl(args.current)

    quality_gate = DatasetQualityGate(
        numeric_fields=(
            "close",
            "volume",
        ),
        min_numeric={
            "close": 0.0,
            "volume": 0.0,
        },
    )

    quality = quality_gate.validate(current)

    drift_detector = DistributionDriftDetector()

    drift = drift_detector.compare(
        reference,
        current,
        fields=(
            "close",
            "volume",
        ),
    )

    print()
    print("DELTA DATA QUALITY AUDIT")
    print("========================")
    print(f"Reference records : {len(reference)}")
    print(f"Current records   : {len(current)}")
    print(f"Quality passed    : {quality.passed}")
    print(
        f"Quality issues    : "
        f"{quality.violation_count}"
    )

    print()
    print("DRIFT")
    print("-----")

    for metric in drift.metrics:
        print(
            f"{metric.field:10} "
            f"status={metric.status:18} "
            f"PSI={metric.psi:.6f} "
            f"mean_shift={metric.mean_shift:.6f} "
            f"std_shift={metric.std_shift:.6f}"
        )


if __name__ == "__main__":
    main()
