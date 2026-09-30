"""P0-6 tests: Alpaca-style streaming lifecycle over simulated paper feed."""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from delta_os.broker_stream import OrderStreamTracker, simulate_paper_feed


def test_stream_full_lifecycle_with_guards():
    t = OrderStreamTracker()
    t.register("c-1")
    out = [t.apply(e) for e in simulate_paper_feed("c-1", 100.0)]
    assert out[0] == "applied:new"
    assert out[1] == "applied:partially_filled"
    assert out[2] == "duplicate_ignored"
    assert out[3] == "late_ignored"
    assert out[4] == "applied:filled"
    assert out[5] == "terminal_preserved"  # late fill after fill: anomaly, state kept
    o = t.orders["c-1"]
    assert o.status == "filled" and o.filled_qty == 100.0
    assert t.stats.applied == 3 and t.stats.duplicates == 1 and t.stats.late == 1
    assert t.stats.anomalies == 1


def test_stream_cancel_reject_disconnect_reconcile():
    t = OrderStreamTracker()
    t.register("c-2")
    assert t.apply({"event_id": "n1", "seq": 1, "client_order_id": "c-2",
                    "event": "new", "filled_qty": 0.0}) == "applied:new"
    assert t.apply({"event_id": "x1", "seq": 2, "client_order_id": "c-2",
                    "event": "canceled", "filled_qty": 0.0}) == "applied:canceled"
    # Fill arriving after cancel must not resurrect the order.
    assert t.apply({"event_id": "f9", "seq": 3, "client_order_id": "c-2",
                    "event": "fill", "filled_qty": 50.0}) == "terminal_preserved"
    assert t.orders["c-2"].status == "canceled"
    # Unknown order + unknown event are contained, never applied.
    assert t.apply({"event_id": "o1", "seq": 1, "client_order_id": "ghost",
                    "event": "fill", "filled_qty": 1.0}) == "orphan_recorded"
    t.register("c-3")
    t.apply({"event_id": "n3", "seq": 1, "client_order_id": "c-3",
             "event": "new", "filled_qty": 0.0})
    flagged = t.note_disconnect()
    assert set(flagged) == {"c-3"}  # terminal c-2 excluded
    assert t.orders["c-3"].needs_reconcile
    t.clear_reconcile("c-3")
    assert not t.orders["c-3"].needs_reconcile
