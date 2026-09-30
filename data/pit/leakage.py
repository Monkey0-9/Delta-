"""PIT leakage battery: automated look-ahead / survivorship / contamination guards.

Wraps the (correct) ``data.pit.construction_pipeline`` primitives with a
research-grade battery that a backtest MUST pass before results are trusted:

1. timestamp_leakage      — decision asof < publication_ts (uses detect_lookahead)
2. revision_leakage        — a revised value visible before its revision_ts
3. universe_survivorship   — members entering the tradable universe late
(listing_ts > first decision date) while their
pre-listing history is present
4. target_leakage          — target column timestamped after the feature asof
5. train_test_contamination— overlapping [train_end, test_start) after embargo
6. corporate_action_timing — split/dividend applied_at > ex_date used early

All checks are deterministic, pandas-only, and return machine-readable
``LeakFinding`` rows. Zero findings = PASS. Any finding = FAIL-CLOSED:
the caller must refuse to promote the experiment.

References (public): Lopez de Prado, *Advances in Financial Machine
Learning* Ch.7 (labeling/PIT, embargo); Bailey et al. on backtest
overfitting; survivorship-bias literature (Brown et al.).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable

import pandas as pd

try:
    from data.pit.construction_pipeline import PITConstructionPipeline
except ImportError:
    from delta.data.pit.construction_pipeline import PITConstructionPipeline  # type: ignore


@dataclass(frozen=True, slots=True)
class LeakFinding:
    check: str
    n_violations: int
    sample_index: tuple
    detail: str


def check_timestamp_leakage(df: pd.DataFrame, asof_col: str = "asof",
                            publish_col: str = "publication_ts") -> LeakFinding:
    bad = PITConstructionPipeline.detect_lookahead(df, asof_col, publish_col)
    return LeakFinding("timestamp_leakage", len(bad), tuple(bad[:5]),
                       "asof < publication_ts: decision used unpublished info")


def check_revision_leakage(df: pd.DataFrame, asof_col: str = "asof",
                           revision_col: str = "revision_ts") -> LeakFinding:
    if revision_col not in df.columns:
        return LeakFinding("revision_leakage", 0, (), "no revision column: skip")
    asof = pd.to_datetime(df[asof_col], utc=True)
    rev = pd.to_datetime(df[revision_col], utc=True)
    bad = list(df.index[asof < rev])
    return LeakFinding("revision_leakage", len(bad), tuple(bad[:5]),
                    "asof predates revision_ts: restated value leaked")


def check_universe_survivorship(members: pd.DataFrame,
                                first_decision: Any) -> LeakFinding:
    """members needs [symbol, listing_ts]. Flags symbols listed AFTER the
    first decision date whose history would otherwise be backfilled."""
    if "listing_ts" not in members.columns:
        return LeakFinding("universe_survivorship", 0, (), "no listing_ts: skip")
    first = pd.Timestamp(first_decision, tz="UTC")
    lst = pd.to_datetime(members["listing_ts"], utc=True)
    bad = members.index[lst > first]
    syms = tuple(members.loc[bad, "symbol"].head(5)) if "symbol" in members.columns else tuple(bad[:5])
    return LeakFinding("universe_survivorship", int(len(bad)), syms,
    "listed after first decision: pre-listing history must be excluded")


def check_target_leakage(features_asof: pd.Series, target_ts: pd.Series) -> LeakFinding:
    fa = pd.to_datetime(features_asof, utc=True)
    tt = pd.to_datetime(target_ts, utc=True)
    bad = list(fa.index[tt <= fa])
    return LeakFinding("target_leakage", len(bad), tuple(bad[:5]),
                       "target_ts <= feature asof: target leaks into features")


def check_train_test_contamination(train_end: Any, test_start: Any,
                                   embargo: str = "5D") -> LeakFinding:
    te = pd.Timestamp(train_end, tz="UTC")
    ts = pd.Timestamp(test_start, tz="UTC")
    gap = ts - te
    need = pd.Timedelta(embargo)
    if gap < need:
        return LeakFinding("train_test_contamination", 1, (),
                           f"embargo violated: gap {gap} < {need}")
    return LeakFinding("train_test_contamination", 0, (), "embargo satisfied")


def check_corporate_action_timing(actions: pd.DataFrame) -> LeakFinding:
    """actions needs [ex_date, applied_at]; applied must be >= ex_date and
    no price row may use the adjusted factor before applied_at (caller joins)."""
    if not {"ex_date", "applied_at"}.issubset(actions.columns):
        return LeakFinding("corporate_action_timing", 0, (), "missing cols: skip")
    ex = pd.to_datetime(actions["ex_date"], utc=True)
    ap = pd.to_datetime(actions["applied_at"], utc=True)
    bad = list(actions.index[ap < ex])
    return LeakFinding("corporate_action_timing", len(bad), tuple(bad[:5]),
                       "applied_at < ex_date: adjustment used before it existed")


def run_leakage_battery(**kwargs: Any) -> list[LeakFinding]:
    """Run the subset of checks for which inputs were supplied.

    Accepted kwargs: frame/asof_col/publish_col, rev_frame/revision_col,
    members/first_decision, features_asof/target_ts, train_end/test_start/
    embargo, actions.
    """
    out: list[LeakFinding] = []
    if "frame" in kwargs:
        out.append(check_timestamp_leakage(kwargs["frame"],
                                          kwargs.get("asof_col", "asof"),
                                          kwargs.get("publish_col", "publication_ts")))
    if "rev_frame" in kwargs:
        out.append(check_revision_leakage(kwargs["rev_frame"],
                                         kwargs.get("asof_col", "asof"),
                                         kwargs.get("revision_col", "revision_ts")))
    if "members" in kwargs and "first_decision" in kwargs:
        out.append(check_universe_survivorship(kwargs["members"], kwargs["first_decision"]))
    if "features_asof" in kwargs and "target_ts" in kwargs:
        out.append(check_target_leakage(kwargs["features_asof"], kwargs["target_ts"]))
    if "train_end" in kwargs and "test_start" in kwargs:
        out.append(check_train_test_contamination(kwargs["train_end"], kwargs["test_start"],
                                                  kwargs.get("embargo", "5D")))
    if "actions" in kwargs:
        out.append(check_corporate_action_timing(kwargs["actions"]))
    return out


def battery_passed(findings: list[LeakFinding]) -> bool:
    return all(f.n_violations == 0 for f in findings)


__all__ = [
    "LeakFinding", "check_timestamp_leakage", "check_revision_leakage",
    "check_universe_survivorship", "check_target_leakage",
    "check_train_test_contamination", "check_corporate_action_timing",
    "run_leakage_battery", "battery_passed",
]
