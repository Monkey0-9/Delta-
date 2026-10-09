"""B9: SRE wiring pins — rules fire on breach, stay silent on healthy,
missing metrics never fire (blindness noted), exporter serves real
delta_* series, and the runbook documents every rule.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")


def _breached_snapshot() -> dict:
    return {"kill_switch_state": 1.0, "risk_latency_ns_p99": 2000000.0,
            "rejection_rate": 0.2, "fill_ratio": 0.1, "queue_depth": 50000.0,
            "drawdown": -0.05, "gaps_total": 3.0}


def _healthy_snapshot() -> dict:
    return {"kill_switch_state": 0.0, "risk_latency_ns_p99": 300000.0,
            "rejection_rate": 0.001, "fill_ratio": 0.98, "queue_depth": 12.0,
            "drawdown": -0.001, "gaps_total": 0.0}


def test_breached_snapshot_fires_criticals():
    from observability.alerts import AlertEngine
    from observability.ops_rules import RULES
    fired = AlertEngine(RULES).evaluate(_breached_snapshot())
    names = {a.rule for a in fired}
    assert {"kill-switch-engaged", "risk-latency-p99-critical",
            "drawdown-breach"} <= names
    assert all(a.value is not None for a in fired)


def test_healthy_snapshot_silent():
    from observability.alerts import AlertEngine
    from observability.ops_rules import RULES
    assert AlertEngine(RULES).evaluate(_healthy_snapshot()) == []


def test_missing_metrics_never_fire_but_noted(tmp_path):
    from sre_check import build_snapshot, run
    from observability.telemetry import Telemetry
    snap, notes, _ = build_snapshot(Telemetry(), kill_state=0)
    assert "fill_ratio" not in snap and "rejection_rate" not in snap
    assert "risk_latency_ns_p99" not in snap
    assert any("blind" in n for n in notes)
    r = run(tmp_path, kill_state=0)
    assert r["verdict"] == "CLEAR"
    assert any("blind" in n for n in r["blindness_notes"])


def test_live_telemetry_flows_to_rules_and_slo():
    from sre_check import build_snapshot, evaluate
    from observability.telemetry import Telemetry
    tel = Telemetry()
    for _ in range(100):
        tel.inc("orders")
    for _ in range(2):
        tel.inc("rejects")
    for _ in range(90):
        tel.inc("fills")
    for v in (3000, 4000, 5000, 6000):
        tel.observe("risk_latency_ns", v)
    snap, notes, risk_us = build_snapshot(tel, kill_state=0)
    assert abs(snap["fill_ratio"] - 0.9) < 1e-9
    assert abs(snap["rejection_rate"] - 0.02) < 1e-9
    ev = evaluate(snap, tuple(risk_us))
    assert ev["fired"] == []  # healthy by every threshold
    assert ev["slos"][0]["status"] == "PASS"


def test_exporter_serves_real_delta_series():
    from observability.exporter import serve_background
    from observability.telemetry import Telemetry
    tel = Telemetry()
    tel.inc("orders", 7)
    tel.set_gauge("queue_depth", 3.0)
    srv, _ = serve_background(tel, port=19311)
    try:
        body = urllib.request.urlopen("http://127.0.0.1:19311/metrics", timeout=5).read().decode()
    finally:
        srv.shutdown()
    assert "delta_orders_total 7" in body
    assert "delta_queue_depth 3" in body


def test_runbook_covers_every_rule():
    from observability.ops_rules import OPS_RULES
    rb = Path("docs/SRE_RUNBOOK.md").read_text(encoding="utf-8")
    for r in OPS_RULES:
        assert r.rule.name in rb, f"runbook missing {r.rule.name}"
        assert r.owner in rb
