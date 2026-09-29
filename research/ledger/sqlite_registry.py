"""Persistent experiment registry — SQLite + immutable manifest + artifact hashes.

Every experiment records:
  EXP-ID, CODE SHA, DATASET SHA, FEATURE/MODEL/PARAM VERSIONS, ENV, SEED,
  TRAIN/VALIDATION/OOS periods, COST/EXECUTION/PORTFOLIO/RISK models, RESULT HASH.

`delta research reproduce EXP-xxx` re-resolves the manifest and re-runs
deterministically. SQLite schema is forward-compatible with a future
Postgres/object-store move (same manifest contract).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def manifest_hash(manifest: dict) -> str:
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                     default=str).encode()
    return hashlib.sha256(raw).hexdigest()


def build_manifest(
    *,
    experiment_id: str,
    hypothesis: str,
    code_sha: str,
    dataset_id: str,
    dataset_sha: str,
    feature_version: str = "f-v1",
    model_version: str = "m-v1",
    param_version: str = "p-v1",
    env: str = "research",
    seed: int = 42,
    train: tuple = ("2014-01-01", "2021-12-31"),
    validation: tuple = ("2022-01-01", "2023-12-31"),
    oos: tuple = ("2024-01-01", "2026-09-29"),
    cost_model: str = "realistic-v1",
    execution_model: str = "vwap-sim-v1",
    portfolio_model: str = "meanvar-v1",
    risk_model: str = "governor-v1",
    config_hash: str = "",
) -> dict:
    m = {
        "experiment_id": experiment_id,
        "hypothesis": hypothesis,
        "code_sha": code_sha,
        "dataset_id": dataset_id,
        "dataset_sha": dataset_sha,
        "feature_version": feature_version,
        "model_version": model_version,
        "param_version": param_version,
        "env": env,
        "seed": seed,
        "train": list(train),
        "validation": list(validation),
        "oos": list(oos),
        "cost_model": cost_model,
        "execution_model": execution_model,
        "portfolio_model": portfolio_model,
        "risk_model": risk_model,
        "config_hash": config_hash,
        "created_at": _utc(),
    }
    m["result_hash"] = ""  # filled on completion
    m["manifest_hash"] = manifest_hash({k: v for k, v in m.items()
                                        if k != "manifest_hash"})
    return m


_SCHEMA = """
CREATE TABLE IF NOT EXISTS experiments (
  experiment_id TEXT PRIMARY KEY,
  manifest TEXT NOT NULL,
  manifest_hash TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'planned',
  result_hash TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
"""


class SqliteRegistry:
    """Durable registry. Default path keeps paper/research state out of /tmp."""

    def __init__(self, path: str | Path = "data/research/experiments.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.execute(_SCHEMA)
        self._db.commit()

    def put(self, manifest: dict, status: str = "planned",
            result: dict | None = None) -> dict:
        mh = manifest.get("manifest_hash") or manifest_hash(manifest)
        rh = manifest_hash(result) if result else manifest.get("result_hash", "")
        now = _utc()
        stored = dict(manifest)
        stored["manifest_hash"] = mh
        stored["result_hash"] = rh
        self._db.execute(
            "INSERT OR REPLACE INTO experiments "
            "(experiment_id, manifest, manifest_hash, status, result_hash,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (stored["experiment_id"], json.dumps(stored, sort_keys=True, default=str),
             mh, status, rh, stored.get("created_at", now), now),
        )
        self._db.commit()
        return stored

    def get(self, experiment_id: str) -> dict | None:
        row = self._db.execute(
            "SELECT manifest, status FROM experiments WHERE experiment_id=?",
            (experiment_id,)).fetchone()
        if not row:
            return None
        m = json.loads(row[0])
        m["_status"] = row[1]
        return m

    def reproduce(self, experiment_id: str) -> dict:
        """Return the exact manifest needed to re-run an experiment."""
        m = self.get(experiment_id)
        if m is None:
            raise KeyError(f"unknown experiment: {experiment_id}")
        expect = manifest_hash({k: v for k, v in m.items()
                                if k not in ("manifest_hash", "_status")})
        if expect != m.get("manifest_hash"):
            raise ValueError(f"manifest tampered for {experiment_id}")
        return m

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._db.execute(
            "SELECT experiment_id, status, updated_at FROM experiments "
            "ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [{"experiment_id": r[0], "status": r[1], "updated_at": r[2]}
                for r in rows]
