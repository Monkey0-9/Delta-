"""B9 (TDD): sre_check CLI wiring — YAML rules, env addr, fail-closed exits.

Sibling tests/test_sre_wiring.py pins the engine (AlertEngine + OPS_RULES);
these pin the CLI contract the task requires:
  * observability/alert_rules.yml mirrors OPS_RULES (+ placeholder contacts);
  * synthetic breach metrics -> exit 1 with reasons;
  * healthy metrics -> exit 0;
  * DELTA_METRICS_ADDR exporter scrape feeds the snapshot.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")

YAML_PATH = "observability/alert_rules.yml"


def _breach():
    return {"kill_switch_state": 1.0, "risk_latency_ns_p99": 2000000.0,
            "rejection_rate": 0.2, "fill_ratio": 0.1}


def test_alert_rules_yaml_mirrors_ops_rules():
    import yaml
    from observability.ops_rules import OPS_RULES
    doc = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    assert doc["contacts"]["pagerduty_routing_key"].startswith("PLACEHOLDER")
    assert doc["contacts"]["slack_webhook_url"].startswith("PLACEHOLDER")
    yrules = {r["name"]: r for r in doc["rules"]}
    assert len(yrules) == len(OPS_RULES)
    for op in OPS_RULES:
        y = yrules[op.rule.name]
        assert y["metric"] == op.rule.metric
        assert y["op"] == op.rule.op
        assert float(y["threshold"]) == op.rule.threshold
        assert y["severity"] == op.rule.severity


def test_yaml_contacts_have_no_real_urls():
    import yaml
    doc = yaml.safe_load(open(YAML_PATH, encoding="utf-8"))
    blob = json.dumps(doc["contacts"])
    assert "http" not in blob, "real webhook URL in contacts"


def test_breach_metrics_exit_nonzero_with_reasons(tmp_path, capsys):
    import sre_check
    mp = tmp_path / "breach.json"
    mp.write_text(json.dumps(_breach()), encoding="utf-8")
    rc = sre_check.main(["--workdir", str(tmp_path / "out"),
                         "--metrics-json", str(mp),
                         "--metrics-addr", "127.0.0.1:1"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "kill-switch-engaged" in out


def test_healthy_metrics_exit_zero(tmp_path):
    import sre_check
    mp = tmp_path / "healthy.json"
    mp.write_text(json.dumps({"kill_switch_state": 0.0,
                              "risk_latency_ns_p99": 3000.0,
                              "rejection_rate": 0.001,
                              "fill_ratio": 0.98,
                              "queue_depth": 12.0,
                              "drawdown": -0.001,
                              "gaps_total": 0.0}), encoding="utf-8")
    rc = sre_check.main(["--workdir", str(tmp_path / "out"),
                         "--metrics-json", str(mp),
                         "--metrics-addr", "127.0.0.1:1"])
    assert rc == 0


def test_exporter_scrape_feeds_snapshot(tmp_path):
    from observability.exporter import serve_background
    from observability.telemetry import Telemetry
    import sre_check
    tel = Telemetry()
    for _ in range(100):
        tel.inc("orders")
    for _ in range(2):
        tel.inc("rejects")
    srv, _ = serve_background(tel, port=19312)
    try:
        r = sre_check.run(tmp_path / "out", kill_state=0,
                          metrics_addr="127.0.0.1:19312")
    finally:
        srv.shutdown()
    assert abs(r["snapshot"]["rejection_rate"] - 0.02) < 1e-9
    assert any("exporter 127.0.0.1:19312" in n for n in r["blindness_notes"]
               + [r.get("source_note", "")])


def test_scrape_failure_falls_back_without_fabrication(tmp_path):
    import sre_check
    r = sre_check.run(tmp_path / "out", kill_state=0,
                      metrics_addr="127.0.0.1:1")
    assert r["verdict"] == "CLEAR"  # empty local telemetry: blind, not breach
    assert any("blind" in n for n in r["blindness_notes"])
    assert "rejection_rate" not in r["snapshot"]
    # Gauges join the snapshot only on observation — empty telemetry must
    # not seed queue_depth/drawdown/gaps_total zeros that read as CLEAR.
    for gauge in ("queue_depth", "drawdown", "gaps_total"):
        assert gauge not in r["snapshot"], f"fabricated {gauge}"
    assert any("queue_depth" in n and "blind" in n
               for n in r["blindness_notes"])
    assert any("drawdown" in n and "blind" in n
               for n in r["blindness_notes"])
    assert any("gaps" in n and "blind" in n for n in r["blindness_notes"])
