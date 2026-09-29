"""PIT query engine: as-of joins and snapshot retrieval.

Pandas/numpy only. Works against in-memory registered frames; an optional
manifest-system handle may be attached for metadata lookups.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

__all__ = ["PITQueryEngine"]


def _as_ts(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


class PITQueryEngine:
    """Serve point-in-time correct views of prices and fundamentals."""

    def __init__(self, manifest_system: Any | None = None) -> None:
        self._manifest_system = manifest_system
        self._frames: dict[str, pd.DataFrame] = {}
        self._publish_cols: dict[str, str] = {}

    def register_snapshot(
        self,
        manifest_id: str,
        df: pd.DataFrame,
        publish_col: str = "publication_ts",
    ) -> None:
        """Register a frame under ``manifest_id`` for PIT queries."""
        if publish_col not in df.columns:
            raise KeyError(f"missing publish_col: {publish_col!r}")
        self._frames[manifest_id] = df.copy()
        self._publish_cols[manifest_id] = publish_col

    def get_snapshot(self, manifest_id: str, asof: Any) -> pd.DataFrame:
        """Return rows of ``manifest_id`` published at or before ``asof``."""
        if manifest_id not in self._frames:
            raise KeyError(f"unknown manifest_id: {manifest_id!r}")
        asof_ts = _as_ts(asof)
        df = self._frames[manifest_id]
        publish_col = self._publish_cols[manifest_id]
        pub = pd.to_datetime(df[publish_col], utc=True)
        mask = np.asarray(pub <= asof_ts)
        return df.loc[mask].reset_index(drop=True)

    def point_in_time_join(
        self,
        prices: pd.DataFrame,
        fundamentals: pd.DataFrame,
        asof: Any,
        price_time_col: str = "timestamp",
        fund_publish_col: str = "publication_ts",
        on: str | list[str] = "symbol",
    ) -> pd.DataFrame:
        """As-of join of prices with the latest known fundamentals.

        For each price row, attaches the most recent fundamental row (per
        ``on`` key) whose publication timestamp is ``<=`` the price time
        and ``<= asof``. Rows with no known fundamental are dropped.

        Args:
            prices: Price frame with ``price_time_col``.
            fundamentals: Fundamental frame with ``fund_publish_col``.
            asof: Decision time cutoff (nothing published after counts).
            price_time_col: Timestamp column of ``prices``.
            fund_publish_col: Publication timestamp column of ``fundamentals``.
            on: Join key column(s), e.g. ``"symbol"``.

        Returns:
            Joined frame sorted by key(s) then price time.
        """
        asof_ts = _as_ts(asof)
        if price_time_col not in prices.columns:
            raise KeyError(f"missing price_time_col: {price_time_col!r}")
        if fund_publish_col not in fundamentals.columns:
            raise KeyError(f"missing fund_publish_col: {fund_publish_col!r}")
        keys = [on] if isinstance(on, str) else list(on)
        for key in keys:
            if key not in prices.columns or key not in fundamentals.columns:
                raise KeyError(f"join key missing: {key!r}")

        px = prices.copy()
        px["_px_ts"] = pd.to_datetime(px[price_time_col], utc=True)
        px = px.loc[px["_px_ts"] <= asof_ts].sort_values("_px_ts")

        fn = fundamentals.copy()
        fn["_fn_pub"] = pd.to_datetime(fn[fund_publish_col], utc=True)
        fn = fn.loc[fn["_fn_pub"] <= asof_ts].sort_values("_fn_pub")
        if px.empty or fn.empty:
            return px.iloc[0:0].drop(columns=["_px_ts"])

        if len(keys) == 1:
            key = keys[0]
            parts: list[pd.DataFrame] = []
            for sym, grp in px.groupby(key, sort=False):
                fgrp = fn.loc[fn[key] == sym]
                if fgrp.empty:
                    continue
                merged = pd.merge_asof(
                    grp.sort_values("_px_ts"),
                    fgrp.sort_values("_fn_pub"),
                    left_on="_px_ts",
                    right_on="_fn_pub",
                    suffixes=("", "_fund"),
                )
                parts.append(merged)
            out = pd.concat(parts, ignore_index=True) if parts else px.iloc[0:0]
        else:
            px["_gkey"] = list(zip(*(px[k] for k in keys)))
            fn["_gkey"] = list(zip(*(fn[k] for k in keys)))
            parts = []
            for gkey, grp in px.groupby("_gkey", sort=False):
                fgrp = fn.loc[fn["_gkey"] == gkey]
                if fgrp.empty:
                    continue
                merged = pd.merge_asof(
                    grp.sort_values("_px_ts"),
                    fgrp.sort_values("_fn_pub").drop(columns=["_gkey"]),
                    left_on="_px_ts",
                    right_on="_fn_pub",
                    suffixes=("", "_fund"),
                )
                parts.append(merged)
            out = pd.concat(parts, ignore_index=True) if parts else px.iloc[0:0]
            out = out.drop(columns=["_gkey"], errors="ignore")

        out = out.drop(columns=["_px_ts", "_fn_pub"], errors="ignore")
        fund_cols = [c for c in fundamentals.columns if c in out.columns]
        out = out.dropna(subset=fund_cols).reset_index(drop=True)
        return out
