from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class LakeConfig:
    root: Path

    @property
    def parquet_root(self) -> Path:
        return self.root / "parquet"

    @property
    def duckdb_path(self) -> Path:
        return self.root / "delta.duckdb"


class ColumnarLake:
    TABLES = (
        "raw",
        "normalized",
        "features",
        "forecasts",
        "signals",
        "orders",
        "fills",
        "risk",
        "benchmarks",
        "experiments",
    )

    def __init__(self, config: LakeConfig):
        self.config = config

        self.config.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        for table in self.TABLES:
            (
                self.config.parquet_root / table
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

    def connect(self):
        return duckdb.connect(
            str(self.config.duckdb_path)
        )

    def write(
        self,
        table: str,
        frame: pd.DataFrame,
    ) -> Path:

        if table not in self.TABLES:
            raise ValueError(
                f"Unknown table: {table}"
            )

        if frame.empty:
            raise ValueError(
                "Cannot persist empty dataframe"
            )

        path = (
            self.config.parquet_root
            / table
            / "data.parquet"
        )

        frame.to_parquet(
            path,
            index=False,
        )

        return path

    def query(self, sql: str) -> pd.DataFrame:

        with self.connect() as con:
            return con.execute(sql).df()

    def health(self) -> dict:

        with self.connect() as con:
            version = con.execute(
                "SELECT version()"
            ).fetchone()[0]

        return {
            "status": "healthy",
            "duckdb": version,
            "root": str(self.config.root),
        }