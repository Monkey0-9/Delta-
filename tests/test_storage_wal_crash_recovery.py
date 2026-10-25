"""Test suite for SQLite WAL and JSONL Crash Recovery."""
import json
from pathlib import Path
import sqlite3
import pytest

from delta_os.paging import PagingDispatcher
from delta_os.storage_recovery import StorageRecoveryEngine


def test_sqlite_wal_integrity_and_checkpoint(tmp_path: Path):
    db_file = tmp_path / "test_trades.sqlite3"
    engine = StorageRecoveryEngine()

    # Create table and insert records
    conn = sqlite3.connect(str(db_file))
    engine.configure_resilient_sqlite(conn)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE orders (id TEXT PRIMARY KEY, qty REAL);")
    cursor.execute("INSERT INTO orders VALUES ('ord-1', 100.0);")
    conn.commit()
    conn.close()

    healthy, msg = engine.verify_and_checkpoint_sqlite(db_file)
    assert healthy is True
    assert "verified healthy" in msg


def test_sqlite_corruption_quarantine(tmp_path: Path):
    db_file = tmp_path / "corrupt_ledger.sqlite3"
    # Write garbage bytes to simulate torn block corruption
    db_file.write_bytes(b"CORRUPT_NOT_A_VALID_SQLITE_HEADER_1234567890")

    alert_log = tmp_path / "alerts.jsonl"
    pager = PagingDispatcher(ledger_path=alert_log)
    engine = StorageRecoveryEngine(pager=pager)

    healthy, msg = engine.verify_and_checkpoint_sqlite(db_file, quarantine_if_corrupt=True)
    assert healthy is False
    assert "QUARANTINED" in msg

    # Original corrupted file should have been moved
    assert not db_file.exists()
    # A corrupt backup must exist
    corrupt_backups = list(tmp_path.glob("corrupt_ledger.sqlite3.corrupt-*"))
    assert len(corrupt_backups) == 1

    # Check that a critical alert was dispatched
    assert alert_log.exists()
    alerts = [json.loads(line) for line in alert_log.read_text().splitlines() if line.strip()]
    assert any(a.get("metadata", {}).get("rule") == "SQLITE_INTEGRITY_FAIL" and a["severity"] == "CRITICAL" for a in alerts)


def test_recover_torn_jsonl_ledger(tmp_path: Path):
    ledger_file = tmp_path / "mistakes.jsonl"
    valid_record_1 = {"symbol": "AAPL", "side": "BUY", "loss": -0.05}
    valid_record_2 = {"symbol": "NVDA", "side": "SELL", "loss": -0.02}

    # Write valid lines followed by a torn/truncated JSON line (kill -9 mid write)
    content = (
        json.dumps(valid_record_1) + "\n" +
        json.dumps(valid_record_2) + "\n" +
        '{"symbol": "MSFT", "side": "BUY", "loss": '  # Torn unclosed JSON line
    )
    ledger_file.write_text(content, encoding="utf-8")

    alert_log = tmp_path / "alerts.jsonl"
    pager = PagingDispatcher(ledger_path=alert_log)
    engine = StorageRecoveryEngine(pager=pager)

    valid_cnt, dropped_cnt, msg = engine.recover_torn_jsonl_ledger(ledger_file)

    assert valid_cnt == 2
    assert dropped_cnt == 1
    assert "REPAIRED" in msg

    # Ledger must now be completely valid JSONL
    lines = [json.loads(l) for l in ledger_file.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert lines[0]["symbol"] == "AAPL"
    assert lines[1]["symbol"] == "NVDA"
