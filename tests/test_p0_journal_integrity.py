"""P0-5: OMS journal must verify the complete integrity contract on replay.

Replay must recompute every record hash (not just check the prev link),
verify sequence continuity and legal state transitions, use full-length
hashes, and refuse tampered / truncated / gapped journals loudly.
"""
from __future__ import annotations

import json
import sys
import threading

import pytest

sys.path.insert(0, ".")

from core.oms.journal import JournalCorruption, OmsJournal


def _write_orders(j: OmsJournal, n: int = 3) -> None:
    for i in range(n):
        oid = f"O{i:04d}"
        j.append(oid, "CREATED")
        j.append(oid, "VALIDATED")


def test_new_hashes_are_full_length(tmp_path):
    j = OmsJournal(tmp_path / "j.jsonl")
    e = j.append("O0001", "CREATED")
    assert len(e.hash) == 64, f"hash must be full SHA-256 hex, got {e.hash!r}"


def test_replay_recomputes_hashes_and_refuses_tamper(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    _write_orders(j, 2)
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[2])
    rec["state"] = "FILLED"  # tamper: VALIDATED -> FILLED without transition
    lines[2] = json.dumps(rec)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(JournalCorruption):
        OmsJournal(p)


def test_replay_rejects_sequence_gap(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    _write_orders(j, 2)
    lines = p.read_text(encoding="utf-8").splitlines()
    del lines[1]  # remove a record -> seq gap
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(JournalCorruption):
        OmsJournal(p)


def test_replay_rejects_illegal_transition_in_file(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    j.append("O0001", "CREATED")
    # Hand-craft a legal-looking but illegal transition with valid hashes.
    from core.oms.journal import _hash

    with open(p, "a", encoding="utf-8") as f:
        prev = json.loads(p.read_text(encoding="utf-8").splitlines()[-1])["hash"]
        seq = 2
        h = _hash(seq, "O0001", "FILLED", "2026-01-01T00:00:00+00:00", prev)
        f.write(json.dumps({"seq": seq, "order_id": "O0001", "state": "FILLED",
                            "at": "2026-01-01T00:00:00+00:00",
                            "prev_hash": prev, "hash": h}) + "\n")
    with pytest.raises(JournalCorruption):
        OmsJournal(p)


def test_truncated_tail_is_refused_not_dropped(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    _write_orders(j, 1)
    with open(p, "ab") as f:
        f.write(b'{"seq": 3, "order_id": "O000')  # torn write, no newline
    with pytest.raises(JournalCorruption):
        OmsJournal(p)


def test_concurrent_appends_keep_strict_sequence(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    errors: list = []

    def worker(n: int) -> None:
        try:
            for i in range(10):
                j.append(f"T{n}-{i}", "CREATED")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors, errors
    seqs = [json.loads(line)["seq"]
            for line in p.read_text(encoding="utf-8").splitlines()]
    assert seqs == list(range(1, 41)), "concurrent appends broke the sequence"
    # Fresh instance must replay the interleaved journal identically.
    replayed = OmsJournal(p).snapshot()
    assert len(replayed) == 40


def test_kill9_reopen_replays_identical_state(tmp_path):
    p = tmp_path / "j.jsonl"
    j = OmsJournal(p)
    _write_orders(j, 3)
    truth = j.snapshot()
    del j  # simulate abrupt termination: no close/flush ceremony
    assert OmsJournal(p).snapshot() == truth
