"""PIT leakage guards (P1 slice, Group 12).

Fail-closed helpers enforcing point-in-time discipline:
  - no bar newer than (as_of - lag) may be *usable* for decisions at as_of
  - train labels overlapping test periods (plus embargo) are rejected
  - time-shuffled placebo diagnostic: persistent performance on shuffled
    labels implies leakage (returns verdict dict, never raises on weak signal)
  - dataset-manifest linker: binds a dataset fingerprint into an immutable
    experiment manifest with code/feature/param/seed/period provenance

All timestamps are timezone-aware datetimes. Bar times / label intervals
are passed as plain data so pandas is never required.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta


class LeakageError(ValueError):
    """Raised when point-in-time discipline is violated (fail-closed)."""


def _tz(dt: datetime, name: str) -> datetime:
    if not isinstance(dt, datetime) or dt.tzinfo is None:
        raise LeakageError(f"{name} must be a timezone-aware datetime.")
    return dt


def pit_usable_mask(bar_times: list[datetime], as_of: datetime,
                    lag: timedelta) -> list[bool]:
    """True for bars usable at `as_of`: bar_ts <= as_of - lag."""
    horizon = _tz(as_of, "as_of") - lag
    return [(_tz(t, "bar_ts") <= horizon) for t in bar_times]


def assert_no_future_bars(bar_times: list[datetime], as_of: datetime,
                          lag: timedelta, *, label: str = "bars") -> int:
    """Fail-closed: every bar used at `as_of` must satisfy the PIT lag.

    Returns the count of usable bars. Raises LeakageError otherwise.
    """
    mask = pit_usable_mask(bar_times, as_of, lag)
    usable = sum(mask)
    if usable != len(bar_times):
        bad = len(bar_times) - usable
        raise LeakageError(
            f"{label}: {bad}/{len(bar_times)} bars newer than as_of - lag "
            f"(as_of={as_of.isoformat()}, lag={lag}).")
    return usable


def assert_embargo_ok(train_start: datetime, train_end: datetime,
                      test_start: datetime, test_end: datetime,
                      embargo: timedelta) -> None:
    """Train labels must not overlap the test window nor its embargo tail."""
    for name, v in (("train_start", train_start), ("train_end", train_end),
                    ("test_start", test_start), ("test_end", test_end)):
        _tz(v, name)
    if train_end < train_start or test_end < test_start:
        raise LeakageError("inverted train/test interval.")
    if embargo < timedelta(0):
        raise LeakageError("embargo must be non-negative.")
    overlaps = train_start <= test_end and train_end >= test_start
    embargoed = train_start <= test_end + embargo and train_end >= test_end
    if overlaps or embargoed:
        raise LeakageError(
            "train interval overlaps test window or embargo tail "
            f"(train=[{train_start.isoformat()}, {train_end.isoformat()}], "
            f"test=[{test_start.isoformat()}, {test_end.isoformat()}], "
            f"embargo={embargo}).")


def shuffle_placebo_diagnostic(is_perf: float, shuffled_perfs: list[float],
                               *, tol: float = 0.0) -> dict:
    """Time-shuffle placebo: if shuffled-label performance matches or beats
    in-sample performance, the pipeline likely leaks time structure.

    Returns {leak_suspect: bool, ...}; never raises on weak signal.
    """
    vals = [float(v) for v in shuffled_perfs
            if v is not None and float(v) == float(v)]
    if not vals or not (float(is_perf) == float(is_perf)):
        return {"leak_suspect": False, "reason": "insufficient-data",
                "n_shuffles": len(vals)}
    import statistics
    mean_shuf = statistics.fmean(vals)
    suspect = mean_shuf + tol + 1e-12 >= float(is_perf)
    return {"leak_suspect": bool(suspect), "is_perf": float(is_perf),
            "shuffled_mean": float(mean_shuf),
            "shuffled_max": float(max(vals)), "n_shuffles": len(vals)}


@dataclass(frozen=True, slots=True)
class LinkedManifest:
    dataset_fingerprint: str
    code_sha: str
    feature_version: str
    param_hash: str
    seed: int
    train_period: str
    validation_period: str
    oos_period: str
    manifest_hash: str

    def verify(self) -> bool:
        return self.manifest_hash == _manifest_hash(
            self.dataset_fingerprint, self.code_sha, self.feature_version,
            self.param_hash, self.seed, self.train_period,
            self.validation_period, self.oos_period)


def _manifest_hash(*parts) -> str:
    raw = json.dumps(list(parts), sort_keys=True, default=str)
    return "MAN-" + hashlib.sha256(raw.encode()).hexdigest()[:12].upper()


def link_dataset_manifest(*, dataset_fingerprint: str, code_sha: str,
                          feature_version: str, params: dict, seed: int,
                          train_period: str, validation_period: str,
                          oos_period: str) -> LinkedManifest:
    """Bind a dataset SHA into experiment provenance (hash-verified)."""
    if not dataset_fingerprint:
        raise LeakageError("dataset_fingerprint is required (no anonymous data).")
    param_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True, default=str).encode()).hexdigest()[:12]
    return LinkedManifest(
        dataset_fingerprint=dataset_fingerprint, code_sha=code_sha,
        feature_version=feature_version, param_hash=param_hash, seed=int(seed),
        train_period=train_period, validation_period=validation_period,
        oos_period=oos_period,
        manifest_hash=_manifest_hash(dataset_fingerprint, code_sha,
                                     feature_version, param_hash, seed,
                                     train_period, validation_period, oos_period))


__all__ = ["LeakageError", "LinkedManifest", "assert_embargo_ok",
           "assert_no_future_bars", "link_dataset_manifest",
           "pit_usable_mask", "shuffle_placebo_diagnostic"]
