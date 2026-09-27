from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json


# ============================================================================
# HELPERS
# ============================================================================

def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(
        _canonical_json(value).encode("utf-8")
    ).hexdigest()


def _parse_timestamp(
    value: object,
    field: str,
) -> datetime:
    if not isinstance(value, str):
        raise ValueError(
            f"{field} must be an ISO-8601 timestamp"
        )

    try:
        result = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"{field} is not a valid ISO-8601 timestamp"
        ) from exc

    if result.tzinfo is None:
        raise ValueError(
            f"{field} must be timezone-aware"
        )

    return result.astimezone(timezone.utc)


# ============================================================================
# EXISTING DELTA DATASET ARTIFACT
# ============================================================================

@dataclass(frozen=True, slots=True)
class DatasetArtifact:
    dataset_id: str
    version: str
    record_count: int
    dataset_hash: str
    records: tuple[dict[str, object], ...]
    leakage_passed: bool
    leakage_violations: int
    source: str


# ============================================================================
# EXISTING DATASET FACTORY
# ============================================================================

class DatasetFactory:
    """
    Backward-compatible DELTA dataset factory.

    Supports:

        DatasetFactory()

        DatasetFactory(strict=False)

        build(...)

        build_from_jsonl(...)
    """

    def __init__(
        self,
        strict: bool = True,
    ) -> None:
        self.strict = strict

    def build(
        self,
        records: Iterable[dict[str, object]],
        *,
        dataset_id: str,
        version: str,
        source: str,
    ) -> DatasetArtifact:

        normalized = []

        for record in records:

            if not isinstance(record, dict):
                raise TypeError(
                    "Each dataset record must be a dictionary"
                )

            normalized.append(dict(record))

        # ---------------------------------------------------------------
        # Duplicate IDs
        # ---------------------------------------------------------------

        seen: set[str] = set()

        for record in normalized:

            record_id = record.get("record_id")

            if record_id is None:

                if self.strict:
                    raise ValueError(
                        "record_id is required"
                    )

                continue

            record_id = str(record_id)

            if record_id in seen:

                if self.strict:
                    raise ValueError(
                        f"Duplicate record_id: {record_id}"
                    )

            seen.add(record_id)

        # ---------------------------------------------------------------
        # Point-in-time / leakage validation
        # ---------------------------------------------------------------

        leakage_violations = 0

        for record in normalized:

            decision_value = record.get(
                "decision_time"
            )

            effective_value = record.get(
                "effective_at"
            )

            if (
                decision_value is None
                or effective_value is None
            ):

                if self.strict:
                    raise ValueError(
                        "decision_time and effective_at are required"
                    )

                continue

            decision_time = _parse_timestamp(
                decision_value,
                "decision_time",
            )

            effective_at = _parse_timestamp(
                effective_value,
                "effective_at",
            )

            if effective_at > decision_time:

                leakage_violations += 1

                if self.strict:
                    raise ValueError(
                        "leakage: effective_at occurs "
                        "after decision_time"
                    )

        # ---------------------------------------------------------------
        # Deterministic ordering
        # ---------------------------------------------------------------

        normalized.sort(
            key=lambda row: (
                str(
                    row.get(
                        "decision_time",
                        "",
                    )
                ),
                str(
                    row.get(
                        "record_id",
                        "",
                    )
                ),
            )
        )

        immutable_records = tuple(
            dict(row)
            for row in normalized
        )

        # ---------------------------------------------------------------
        # Deterministic dataset hash
        # ---------------------------------------------------------------

        dataset_hash = _sha256(
            {
                "dataset_id": dataset_id,
                "version": version,
                "source": source,
                "records": normalized,
            }
        )

        return DatasetArtifact(
            dataset_id=dataset_id,
            version=version,
            record_count=len(
                immutable_records
            ),
            dataset_hash=dataset_hash,
            records=immutable_records,
            leakage_passed=(
                leakage_violations == 0
            ),
            leakage_violations=leakage_violations,
            source=source,
        )

    def build_from_jsonl(
        self,
        path: str | Path,
        *,
        dataset_id: str,
        version: str,
        source: str | None = None,
    ) -> DatasetArtifact:

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                str(path)
            )

        records = []

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:

            for line_number, line in enumerate(
                file,
                start=1,
            ):

                line = line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSONL at line {line_number}"
                    ) from exc

                if not isinstance(record, dict):
                    raise ValueError(
                        f"JSONL line {line_number} "
                        "must contain an object"
                    )

                records.append(record)

        return self.build(
            records,
            dataset_id=dataset_id,
            version=version,
            source=(
                source
                if source is not None
                else str(path)
            ),
        )


# ============================================================================
# W50 FINANCE MODEL DATASET
# ============================================================================

@dataclass(frozen=True, slots=True)
class FinanceExample:
    """
    W50 finance-model example.

    `asof` is the public point-in-time timestamp.
    """

    example_id: str
    task: str
    prompt: str
    target: str
    evidence_ids: tuple[str, ...]
    asof: str | datetime
    asset: str | None = None
    label: str | None = None
    split: str = "train"

    def __post_init__(self) -> None:

        if not self.example_id:
            raise ValueError(
                "example_id is required"
            )

        if not self.task:
            raise ValueError(
                "task is required"
            )

        if not self.prompt:
            raise ValueError(
                "prompt is required"
            )

        if not self.target:
            raise ValueError(
                "target is required"
            )

        if not self.evidence_ids:
            raise ValueError(
                "at least one evidence_id is required"
            )

        timestamp = (
            _parse_timestamp(
                self.asof,
                "asof",
            )
            if isinstance(self.asof, str)
            else self.asof
        )

        if not isinstance(
            timestamp,
            datetime,
        ):
            raise TypeError(
                "asof must be a datetime or ISO timestamp"
            )

        if timestamp.tzinfo is None:
            raise ValueError(
                "asof must be timezone-aware"
            )

        timestamp = timestamp.astimezone(
            timezone.utc
        )

        if self.split not in {
            "train",
            "validation",
            "test",
        }:
            raise ValueError(
                f"invalid split: {self.split}"
            )

        object.__setattr__(
            self,
            "asof",
            timestamp.isoformat(),
        )

        object.__setattr__(
            self,
            "evidence_ids",
            tuple(
                sorted(
                    self.evidence_ids
                )
            ),
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "example_id": self.example_id,
            "task": self.task,
            "prompt": self.prompt,
            "target": self.target,
            "evidence_ids": list(
                self.evidence_ids
            ),
            "asof": self.asof,
            "asset": self.asset,
            "label": self.label,
            "split": self.split,
        }


class FinanceDatasetFactory:

    def __init__(
        self,
        dataset_version: str,
    ) -> None:

        if not dataset_version:
            raise ValueError(
                "dataset_version is required"
            )

        self.dataset_version = dataset_version

    def validate(
        self,
        examples: Iterable[FinanceExample],
    ) -> list[FinanceExample]:

        output = []
        seen = set()

        for example in examples:

            if example.example_id in seen:
                raise ValueError(
                    f"duplicate example_id: "
                    f"{example.example_id}"
                )

            seen.add(
                example.example_id
            )

            output.append(example)

        return output

    def fingerprint(
        self,
        examples: Iterable[FinanceExample],
    ) -> str:

        rows = self.validate(
            examples
        )

        canonical_rows = [
            example.canonical()
            for example in sorted(
                rows,
                key=lambda x: x.example_id,
            )
        ]

        return _sha256(
            {
                "dataset_version":
                    self.dataset_version,
                "rows":
                    canonical_rows,
            }
        )

    def write_jsonl(
        self,
        examples: Iterable[FinanceExample],
        path: str | Path,
    ) -> str:

        rows = self.validate(
            examples
        )

        digest = self.fingerprint(
            rows
        )

        path = Path(path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as file:

            for example in rows:
                file.write(
                    json.dumps(
                        example.canonical(),
                        sort_keys=True,
                    )
                    + "\n"
                )

        return digest

    @staticmethod
    def deterministic_split(
        examples: list[FinanceExample],
        train: float = 0.8,
        valid: float = 0.1,
    ) -> dict[str, list[FinanceExample]]:

        if not (
            0 < train < 1
            and 0 <= valid < 1
            and train + valid < 1
        ):
            raise ValueError(
                "invalid split fractions"
            )

        buckets = {
            "train": [],
            "valid": [],
            "test": [],
        }

        for example in examples:

            number = (
                int(
                    hashlib.sha256(
                        example.example_id.encode(
                            "utf-8"
                        )
                    ).hexdigest()[:8],
                    16,
                )
                / 2**32
            )

            if number < train:
                bucket = "train"
            elif number < train + valid:
                bucket = "valid"
            else:
                bucket = "test"

            buckets[bucket].append(
                example
            )

        return buckets