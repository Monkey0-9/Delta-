from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from decimal import Decimal

from benchmark.workloads import (
    benchmark,
    checksum,
    deterministic_workload,
)


def numerical_workload(size: int) -> str:
    values = deterministic_workload(size)

    transformed = tuple(
        value * value + Decimal("1")
        for value in values
    )

    return checksum(transformed)


def run(size: int, iterations: int) -> dict[str, object]:
    result = benchmark(
        name=f"decimal_numerical_{size}",
        function=lambda: numerical_workload(size),
        iterations=iterations,
    )

    return asdict(result)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DELTA performance benchmark"
    )

    parser.add_argument(
        "--size",
        type=int,
        default=10_000,
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
    )

    args = parser.parse_args()

    result = run(
        size=args.size,
        iterations=args.iterations,
    )

    print(json.dumps(result, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())