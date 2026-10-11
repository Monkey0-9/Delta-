"""P0-1: PIT store must never destroy existing data on reopen.

Regression coverage for the destructive-initialization defect: the SQLite
initializer dropped ticks/snapshots tables on every construction, so
reopening a persistent database erased all research data.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, ".")

from data.tick_pit import DataTimestamps, PITQuery, PITStore, Quote, TickData


def _sample_tick(symbol: str = "AAPL", seq: int = 0) -> tuple[TickData, DataTimestamps]:
    quote = Quote(
        symbol=symbol,
        exchange="NYSE",
        bid_price=150.0 + seq * 0.01,
        ask_price=150.05 + seq * 0.01,
        bid_size=1000,
        ask_size=1000,
    )
    tick = TickData.from_quote(quote)
    now = datetime.now(timezone.utc)
    ts = DataTimestamps(
        event_time=now - timedelta(seconds=10),
        source_timestamp=now - timedelta(seconds=8),
        publication_timestamp=now - timedelta(seconds=5),
        available_timestamp=now - timedelta(seconds=1),
    )
    return tick, ts


def test_reopen_preserves_ticks_and_snapshots(tmp_path):
    db = str(tmp_path / "pit.db")
    store = PITStore(db_path=db)
    for i in range(5):
        tick, ts = _sample_tick(seq=i)
        store.store_tick(tick, ts, source="TEST")
    q = PITQuery(symbol="AAPL", as_of=datetime.now(timezone.utc))
    snap_id = store.create_snapshot(q)
    store.close()

    # Reopen the SAME file: data must survive.
    reopened = PITStore(db_path=db)
    try:
        snap = reopened.query_as_of(q)
        assert len(snap.ticks) == 5, (
            f"data loss on reopen: expected 5 ticks, got {len(snap.ticks)}")
        assert reopened.get_snapshot(snap_id) is not None, (
            "snapshot lost on reopen")
    finally:
        reopened.close()


def test_startup_is_non_destructive_and_versioned(tmp_path):
    db = str(tmp_path / "pit.db")
    store = PITStore(db_path=db)
    tick, ts = _sample_tick()
    store.store_tick(tick, ts, source="TEST")
    store.close()

    reopened = PITStore(db_path=db)
    try:
        with sqlite3.connect(db) as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "ticks" in tables and "snapshots" in tables
        assert "schema_version" in tables, (
            "store must track schema_version for migrations")
        snap = reopened.query_as_of(
            PITQuery(symbol="AAPL", as_of=datetime.now(timezone.utc)))
        assert len(snap.ticks) == 1
    finally:
        reopened.close()


def test_backup_restore_roundtrip(tmp_path):
    import shutil

    db = tmp_path / "pit.db"
    store = PITStore(db_path=str(db))
    for i in range(3):
        tick, ts = _sample_tick(seq=i)
        store.store_tick(tick, ts, source="TEST")
    store.close()

    backup = tmp_path / "pit.backup.db"
    shutil.copy2(db, backup)
    # Simulate loss: destroy the original, restore from backup.
    db.unlink()
    shutil.copy2(backup, db)

    restored = PITStore(db_path=str(db))
    try:
        snap = restored.query_as_of(
            PITQuery(symbol="AAPL", as_of=datetime.now(timezone.utc)))
        assert len(snap.ticks) == 3, "backup restore lost ticks"
    finally:
        restored.close()
