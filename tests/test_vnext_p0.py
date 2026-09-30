"""P0 regression: venue-aware L3 replace, latency methodology, modes, workstation."""
from __future__ import annotations

from decimal import Decimal

from simulation.l3_engine import L3Book, L3Event, ReplacePriorityPolicy


def _add(book, oid, side="buy", price="100", qty="10", seq=1):
    book.apply(L3Event(seq=seq, ts_ns=seq, kind="ADD", order_id=oid,
                       side=side, price=Decimal(price), qty=Decimal(qty)))


def test_replace_decrease_retains_priority():
    b = L3Book(policy=ReplacePriorityPolicy.RETAIN_IF_DECREASE)
    _add(b, "a", seq=1)
    _add(b, "b", seq=2)
    assert b.queue_position("b") == 1
    b.apply(L3Event(seq=3, ts_ns=3, kind="REPLACE", order_id="b",
                    side="buy", price=Decimal("100"), qty=Decimal("5")))
    assert b.queue_position("b") == 1  # retained
    assert b.queue_ahead_qty("b") == Decimal("10")


def test_replace_increase_loses_priority():
    b = L3Book(policy=ReplacePriorityPolicy.RETAIN_IF_DECREASE)
    _add(b, "a", seq=1)
    _add(b, "b", seq=2)
    b.apply(L3Event(seq=3, ts_ns=3, kind="REPLACE", order_id="b",
                    side="buy", price=Decimal("100"), qty=Decimal("50")))
    assert b.queue_position("b") == 1  # cancel+add -> back (still idx 1 of 2)
    # head must now be 'a'
    assert b.queue_position("a") == 0


def test_lose_priority_policy_always_back():
    b = L3Book(policy=ReplacePriorityPolicy.LOSE_PRIORITY)
    _add(b, "a", seq=1)
    _add(b, "b", seq=2)
    b.apply(L3Event(seq=3, ts_ns=3, kind="REPLACE", order_id="b",
                    side="buy", price=Decimal("100"), qty=Decimal("5")))
    assert b.queue_position("a") == 0
    assert b.queue_position("b") == 1


def test_latency_separates_modelled_from_compute():
    from simulation.market_simulator.latency_model import (
        LatencyDistribution, LatencyModel)
    m = LatencyModel(distribution=LatencyDistribution.FIXED,
                     network_latency_ms=0.5, processing_latency_ms=0.1,
                     queue_latency_ms=0.2)
    meas = m.measure_latency("TOTAL")
    assert meas.simulated_latency_ms == meas.latency_ms > 0
    assert meas.compute_ms >= 0.0
    # modelled value must be the configured total, not CPU time
    assert abs(meas.simulated_latency_ms - 0.8) < 1e-9
    assert meas.compute_ms < meas.simulated_latency_ms


def test_modes_parse_and_banner():
    from config.mode import DeltaMode, mode_banner
    assert DeltaMode.parse("paper") is DeltaMode.PAPER
    assert DeltaMode.parse("PROD") is DeltaMode.LIVE
    assert "SYNTHETIC" in mode_banner(DeltaMode.DEMO)


def test_workstation_dispatch_typed_viewmodels():
    from delta_tui.app import DeltaApp
    app = DeltaApp()
    out = app.dispatch("/book NVDA")
    assert "BOOK NVDA" in out and "PAPER" in out
    assert app.store.workspace == "book"
    vm = app.store.viewmodels["book"]
    assert vm.symbol == "NVDA" and hasattr(vm, "imbalance")
    # kill two-step, bypasses LLM
    step1 = app.dispatch("/kill")
    assert "CONFIRM" in step1
    step2 = app.dispatch("/kill CONFIRM")
    # Implementation renders the HALTED box ("EXECUTION HALTED", orders
    # BLOCKED) — assert that wording, not the stale "ENGAGED" string.
    assert "HALTED" in step2 and "BLOCKED" in step2


def test_sqlite_registry_roundtrip_and_reproduce(tmp_path):
    from research.ledger.sqlite_registry import SqliteRegistry, build_manifest
    reg = SqliteRegistry(tmp_path / "exp.sqlite")
    m = build_manifest(experiment_id="EXP-T1", hypothesis="h",
                       code_sha="abc", dataset_id="d",
                       dataset_sha="def")
    reg.put(m, status="planned")
    back = reg.reproduce("EXP-T1")
    assert back["experiment_id"] == "EXP-T1"
    assert back["manifest_hash"] == m["manifest_hash"]
