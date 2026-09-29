"""PIT construction pipeline: asof assignment, snapshot builds, lookahead checks.

Conventions follow data/pit/factory.py and data/pit/manifest_system.py:
timezone-aware timestamps, immutable snapshots, pandas/numpy only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable

import numpy as np
import pandas as pd

__all__ = [
    "PITFrameSnapshot",
    "PITConstructionPipeline",
]


@dataclass(frozen=True, slots=True)
class PITFrameSnapshot:
    """Immutable point-in-time snapshot of a DataFrame."""

    asof: pd.Timestamp
    publication_ts: pd.Timestamp
    data: pd.DataFrame = field(compare=False)
    n_eligible: int = 0
    n_excluded: int = 0


def _as_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


class PITConstructionPipeline:
    """Build point-in-time snapshots from event frames with publish lag.

    A row is eligible at ``asof`` only when its publication timestamp
    (event time + publish lag) is ``<= asof``.
    """

    def __init__(self, default_lag: str = "0D") -> None:
        self._default_lag = pd.Timedelta(default_lag)

    @property
    def default_lag(self) -> pd.Timedelta:
        return self._default_lag

    def assign_asof(
        self,
        df: pd.DataFrame,
        event_time_col: str = "event_time",
        asof_col: str = "asof",
        publish_col: str = "publication_ts",
        lag: str | pd.Timedelta | None = None,
    ) -> pd.DataFrame:
        """Stamp ``asof`` (= event time) and ``publication_ts`` columns.

        Args:
            df: Source frame containing ``event_time_col``.
            event_time_col: Column with the event occurrence time.
            asof_col: Output column for the as-of timestamp.
            publish_col: Output column for event time + publish lag.
            lag: Publish lag; defaults to the pipeline ``default_lag``.

        Returns:
            Copy of ``df`` with ``asof_col`` and ``publish_col`` added.
        """
        if event_time_col not in df.columns:
            raise KeyError(f"missing event_time_col: {event_time_col!r}")
        delta = pd.Timedelta(lag) if lag is not None else self._default_lag
        out = df.copy()
        event_ts = pd.to_datetime(out[event_time_col], utc=True)
        out[asof_col] = event_ts
        out[publish_col] = event_ts + delta
        return out

    def build_snapshot(
        self,
        df: pd.DataFrame,
        asof: Any,
        publish_lag: str | pd.Timedelta | None = None,
        event_time_col: str = "event_time",
        publish_col: str | None = None,
    ) -> PITFrameSnapshot:
        """Build the PIT-eligible snapshot visible at ``asof``.

        Args:
            df: Source frame. Must carry ``publish_col``, otherwise the
                publication timestamp is derived as event time + lag.
            asof: Decision time; only rows published ``<= asof`` qualify.
            publish_lag: Lag applied when ``publish_col`` is absent.
            event_time_col: Event-time column used for lag derivation.
            publish_col: Pre-computed publication column (optional).

        Returns:
            PITFrameSnapshot with ``asof``/``publication_ts`` timestamps.
        """
        asof_ts = _as_ts(asof)
        if publish_col is not None and publish_col in df.columns:
            pub = pd.to_datetime(df[publish_col], utc=True)
            base = df
        else:
            delta = (
                pd.Timedelta(publish_lag)
                if publish_lag is not None
                else self._default_lag
            )
            if event_time_col not in df.columns:
                raise KeyError(f"missing event_time_col: {event_time_col!r}")
            base = df.copy()
            pub = pd.to_datetime(base[event_time_col], utc=True) + delta
        mask = np.asarray(pub <= asof_ts)
        eligible = base.loc[mask].copy()
        return PITFrameSnapshot(
            asof=asof_ts,
            publication_ts=asof_ts,
            data=eligible.reset_index(drop=True),
            n_eligible=int(mask.sum()),
            n_excluded=int((~mask).sum()),
        )

    @staticmethod
    def detect_lookahead(
        df: pd.DataFrame,
        asof_col: str,
        publish_col: str,
    ) -> list[Hashable]:
        """Find rows used before they were published.

        A row is a lookahead violation when ``asof_col < publish_col``,
        i.e. the decision time predates the information release.

        Returns:
            List of index labels of violating rows (empty when clean).
        """
        if asof_col not in df.columns:
            raise KeyError(f"missing asof_col: {asof_col!r}")
        if publish_col not in df.columns:
            raise KeyError(f"missing publish_col: {publish_col!r}")
        asof_ts = pd.to_datetime(df[asof_col], utc=True)
        pub_ts = pd.to_datetime(df[publish_col], utc=True)
        bad = df.index[asof_ts < pub_ts]
        return list(bad)
