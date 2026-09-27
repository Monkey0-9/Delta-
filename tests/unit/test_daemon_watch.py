"""P2: daemon watch verdicts + safe-restart reconciliation."""
from __future__ import annotations

from apps.daemon.reconciler import reconcile_orders
from apps.daemon.watch import WatchInput, evaluate_watch


def test_watch_ok():
    v = evaluate_watch(WatchInput(top_weight=0.02, sector_weight=0.10))
    assert v.state == "OK" and v.execute is False


def test_watch_approaching_no_action():
    v = evaluate_watch(WatchInput(top_weight=0.09, sector_weight=0.38))
    assert v.state == "APPROACHING" and v.execute is False


def test_watch_breach_supervised_alerts_only():
    v = evaluate_watch(
        WatchInput(top_weight=0.50, sector_weight=0.10, execution_mode="SUPERVISED")
    )
    assert v.state == "BREACH" and v.execute is False
    assert any("does not authorize" in a for a in v.actions)


def test_watch_breach_autonomous_executes_when_fresh_and_authorized():
    v = evaluate_watch(
        WatchInput(
            top_weight=0.50,
            sector_weight=0.10,
            execution_mode="AUTONOMOUS",
            authorization_valid=True,
        )
    )
    assert v.state == "BREACH" and v.execute is True


def test_watch_halted_on_stale_or_kill():
    assert evaluate_watch(WatchInput(top_weight=0.9, data_fresh=False)).state == "HALTED"
    assert (
        evaluate_watch(WatchInput(top_weight=0.9, kill_switch_active=True)).state
        == "HALTED"
    )
    v = evaluate_watch(
        WatchInput(top_weight=0.9, execution_mode="AUTONOMOUS", authorization_valid=False)
    )
    assert v.state == "BREACH" and v.execute is False


def test_reconcile_resume_when_agree():
    rep = reconcile_orders(("a", "b"), ("b", "a"))
    assert rep.decision == "RESUME"


def test_reconcile_halts_on_divergence():
    rep = reconcile_orders(("a", "c"), ("a", "b"))
    assert rep.decision == "HALT"
    assert rep.oms_only == ("c",) and rep.broker_only == ("b",)
