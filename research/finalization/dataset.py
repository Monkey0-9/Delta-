from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "date",
    "asset",
    "close",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def validate_price_data(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    if df.empty:
        raise ValueError("Dataset is empty.")

    df["date"] = pd.to_datetime(
        df["date"],
        utc=True,
        errors="raise",
    )

    if df["asset"].isna().any():
        raise ValueError("Null asset detected.")

    if df["close"].isna().any():
        raise ValueError("Null close detected.")

    if (df["close"] <= 0).any():
        raise ValueError("Non-positive close detected.")

    if df.duplicated(
        subset=["date", "asset"]
    ).any():
        raise ValueError(
            "Duplicate date/asset observation detected."
        )


def create_snapshot(
    source: Path,
    destination: Path,
) -> dict[str, Any]:

    df = pd.read_csv(source)

    validate_price_data(df)

    df["date"] = pd.to_datetime(
        df["date"],
        utc=True,
    )

    df = df.sort_values(
        ["date", "asset"]
    ).reset_index(drop=True)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        destination,
        index=False,
    )

    return {
        "source": str(source),
        "snapshot": str(destination),
        "sha256": file_sha256(destination),
        "rows": int(len(df)),
        "assets": sorted(
            df["asset"].astype(str).unique().tolist()
        ),
        "start": df["date"].min().isoformat(),
        "end": df["date"].max().isoformat(),
    }


def write_dataset_manifest(
    source: Path,
    snapshot: Path,
    output: Path,
) -> None:

    manifest = create_snapshot(
        source,
        snapshot,
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
