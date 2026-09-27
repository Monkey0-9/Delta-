"""Append-only SQLite trial registry: historical N for the Deflated Sharpe Ratio.

Multi-session research must count every hypothesis ever tested, not just those
in RAM. DSR's null (expected max Sharpe) grows with N; forgetting trials
flatters snooped strategies. This ledger makes N cumulative and auditable.
Fail-closed: DB errors raise, never silently approve.
"""
from __future__ import annotations
import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from delta_omega.alpha_risk import deflated_sharpe

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    hypothesis_sha TEXT NOT NULL,
    sr REAL NOT NULL,
    t_obs INTEGER NOT NULL,
    skew REAL NOT NULL,
    kurt REAL NOT NULL,
    n_at_test INTEGER NOT NULL,
    dsr REAL NOT NULL,
    verdict TEXT NOT NULL,
    code_sha TEXT NOT NULL DEFAULT '',
    dataset_hash TEXT NOT NULL DEFAULT ''
);
"""

@dataclass(frozen=True, slots=True)
class TrialRecord:
    id: int; hypothesis: str; sr: float; dsr: float; verdict: str; n_at_test: int

class TrialRegistry:
    """Append-only experiment ledger. Trials are never updated or deleted."""

    def __init__(self, path: str | Path = "artifacts/delta_omega/experiments.sqlite3") -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(self._path))
        try:
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute(SCHEMA)
            self._db.commit()
        except Exception:
            self._db.close()
            raise

    def close(self) -> None:
        self._db.close()

    def trial_count(self) -> int:
        row = self._db.execute("SELECT COUNT(*) FROM trials").fetchone()
        return int(row[0])

    def record(self, hypothesis: str, sr: float, t_obs: int, skew: float, kurt: float,
               code_sha: str = "", dataset_hash: str = "", bar: float = 0.99) -> TrialRecord:
        """Append one hypothesis test. N = registry count AFTER insert (this trial counts)."""
        if not hypothesis or not hypothesis.strip():
            raise ValueError("hypothesis text required (no anonymous trials)")
        n = self.trial_count() + 1  # this candidate counts: N is cumulative across sessions
        dsr = float(deflated_sharpe(float(sr), n, int(t_obs), float(skew), float(kurt)))
        verdict = "PASS" if dsr >= bar else "REJECT"
        sha = hashlib.sha256(hypothesis.encode()).hexdigest()[:16]
        cur = self._db.execute(
            "INSERT INTO trials (ts, hypothesis, hypothesis_sha, sr, t_obs, skew, kurt, n_at_test, dsr, verdict, code_sha, dataset_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), hypothesis, sha, float(sr), int(t_obs),
             float(skew), float(kurt), n, dsr, verdict, code_sha, dataset_hash))
        self._db.commit()
        return TrialRecord(int(cur.lastrowid), hypothesis, float(sr), dsr, verdict, n)

    def dsr_with_registry(self, sr: float, t_obs: int, skew: float, kurt: float) -> float:
        """DSR evaluated at N = registered trials + 1 (the candidate counts too)."""
        return float(deflated_sharpe(float(sr), self.trial_count() + 1, int(t_obs), float(skew), float(kurt)))

    def history(self, limit: int = 100) -> list[TrialRecord]:
        rows = self._db.execute(
            "SELECT id, hypothesis, sr, dsr, verdict, n_at_test FROM trials ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
        return [TrialRecord(r[0], r[1], r[2], r[3], r[4], r[5]) for r in rows]
