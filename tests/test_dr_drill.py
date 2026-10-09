"""B9: DR drill pins — recovery is real, timed, and fail-closed.

Runs scripts/dr_drill.py in tmp isolation (never the repo workdir):
RPO=0, replay==truth, reconcile RESUME, tamper refused, RTO<60s, and the
emitted artifact is hash-valid. Also pins the crash-window CANCELLED edge.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")


def test_drill_passes_with_zero_rpo(tmp_path):
    from dr_drill import run
    r = run(tmp_path, n_orders=10)
    assert r["verdict"] == "PASS", r
    assert r["rpo_lost_lines"] == 0
    assert r["replay_match"] is True
    assert r["reconcile_clean"] is True
    assert r["reconcile_decision"] == "RESUME"
    assert r["tamper_refused"] is True
    assert r["rto_s"] < 60.0
    assert r["caught_up_filled"] + r["caught_up_cancelled"] == r["open_before"]
    assert r["open_after"] == 0


def test_drill_artifact_hash_valid(tmp_path):
    from dr_drill import run
    r = run(tmp_path, n_orders=5)
    p = Path(r["artifact"])
    assert p.exists()
    payload = json.loads(p.read_text(encoding="utf-8"))
    h = payload.pop("hash")
    assert hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest() == h


def test_drill_crash_window_orders_cancelled_not_lost(tmp_path):
    from dr_drill import run
    from core.oms.journal import OmsJournal
    r = run(tmp_path, n_orders=5)
    assert r["caught_up_cancelled"] == 1  # i%5==2 of 5 orders
    snap = OmsJournal(tmp_path / "oms.jsonl").snapshot()
    cancelled = [o for o, s in snap.items() if s == "CANCELLED"]
    assert len(cancelled) == 1
    # Cancelled crash-window order never reached the broker book.
    assert cancelled[0] not in [f"DR-{i:03d}" for i in (0, 1, 3, 4)]


def test_journal_state_machine_allows_recovery_cancel():
    from core.oms.journal import VALID_NEXT
    assert "CANCELLED" in VALID_NEXT["SUBMITTED"]
    # Previously-illegal edges still raise (no weakening of the machine).
    import pytest
    from core.oms.journal import OmsJournal
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        j = OmsJournal(Path(td) / "j.jsonl")
        j.append("O-1", "CREATED")
        with pytest.raises(ValueError):
            j.append("O-1", "FILLED")
