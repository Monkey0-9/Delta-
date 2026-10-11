"""B9: SRE check — wire live sources into the ops rules + SLO gates.

Snapshot sources (all real, all guarded, in priority order):
  1. --metrics-json file (synthetic injection for drills/tests);
  2. Prometheus scrape of $DELTA_METRICS_ADDR (default 127.0.0.1:9108,
     served by observability/exporter.py) — delta_orders/rejects/fills
     totals, delta_queue_depth/drawdown gauges, delta_risk_latency_ns_p99;
  3. local fallback: fresh observability.telemetry.Telemetry (empty, so its
     metrics are reported blind, never fabricated) + delta_os.safety kill
     auto-detect (override with --kill-state).
Rule thresholds live in observability/alert_rules.yml (env DELTA_ALERT_RULES
overrides the path) and MUST mirror observability/ops_rules.py OPS_RULES.
A source that cannot be read omits its metrics (rules skip missing metrics
without firing) and records a blindness note — never a fabricated zero.
Exit code: 0 CLEAR, 1 WARN/ALERT (fail-closed, reasons printed).
Emits a hash-chained artifact at <workdir>/sre.json (default artifacts/sre).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, ".")

DEFAULT_METRICS_ADDR = "127.0.0.1:9108"
RULES_PATH = Path(__file__).resolve().parent.parent / "observability" / "alert_rules.yml"


def rules_path() -> Path:
    return Path(os.environ.get("DELTA_ALERT_RULES", RULES_PATH))


def load_alert_rules(path: Path | None = None) -> tuple[dict, tuple]:
    import yaml
    from observability.alerts import AlertRule
    doc = yaml.safe_load((path or rules_path()).read_text(encoding="utf-8"))
    contacts = dict(doc.get("contacts", {}))
    rules = tuple(AlertRule(str(r["name"]), str(r["metric"]), str(r["op"]),
                            float(r["threshold"]), str(r.get("severity", "warning")))
                  for r in doc["rules"])
    return contacts, rules


def scrape_exporter(addr: str, timeout_s: float = 2.0) -> dict[str, float]:
    """Scrape http://<addr>/metrics, return {delta_series: value} floats."""
    import re

    from core.net import urlopen_checked

    if not re.fullmatch(r"[A-Za-z0-9._-]+(:\d+)?", addr):
        raise ValueError(f"refusing suspicious metrics address: {addr!r}")
    with urlopen_checked(f"http://{addr}/metrics", timeout=timeout_s) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    vals: dict[str, float] = {}
    for line in body.splitlines():
        if not line.startswith("delta_"):
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            vals[parts[0]] = float(parts[1])
        except ValueError:
            continue
    return vals


def snapshot_from_scrape(vals: dict[str, float]) -> tuple[dict, list[str]]:
    """Derive the rule snapshot from scraped delta_* series (guarded subset)."""
    snap: dict[str, float] = {}
    notes: list[str] = []
    orders = vals.get("delta_orders_total", 0.0)
    if orders > 0:
        snap["rejection_rate"] = vals.get("delta_rejects_total", 0.0) / orders
        snap["fill_ratio"] = vals.get("delta_fills_total", 0.0) / orders
    else:
        notes.append("blind: exporter shows no orders — ratio rules skipped (no false alarm)")
    for gauge, metric in (("delta_queue_depth", "queue_depth"),
                          ("delta_drawdown", "drawdown"),
                          ("delta_gaps_total", "gaps_total"),
                          ("delta_risk_latency_ns_p99", "risk_latency_ns_p99")):
        if gauge in vals:
            snap[metric] = vals[gauge]
        else:
            notes.append(f"blind: exporter lacks {gauge} — {metric} rule skipped")
    return snap, notes


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _pctl(vals: list[int], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return float(s[min(len(s) - 1, int(len(s) * p))])


def build_snapshot(telemetry=None, kill_state: int | None = None) -> tuple[dict, list[str], tuple]:
    from observability.telemetry import Telemetry
    notes: list[str] = []
    tel = telemetry or Telemetry()
    # Gauges/counters join the snapshot ONLY when actually observed — an
    # absent gauge is blindness (rule skipped + note), never a 0.0 that
    # would read as a healthy CLEAR. Same policy as the ratio/latency paths.
    snap: dict[str, float] = {}
    if "queue_depth" in tel.gauges:
        snap["queue_depth"] = float(tel.gauges["queue_depth"])
    else:
        notes.append("blind: no queue_depth gauge observed — queue rule skipped")
    if "drawdown" in tel.gauges:
        snap["drawdown"] = float(tel.gauges["drawdown"])
    else:
        notes.append("blind: no drawdown gauge observed — drawdown rule skipped")
    if "gaps" in tel.counters:
        snap["gaps_total"] = float(tel.counters["gaps"])
    else:
        notes.append("blind: no gaps counter observed — gaps rule skipped")
    if tel.counters.get("orders", 0):
        snap["rejection_rate"] = tel.rejection_rate()
        snap["fill_ratio"] = tel.fill_ratio()
    else:
        notes.append("blind: no orders observed — ratio rules skipped (no false alarm)")
    risk = tel.histograms.get("risk_latency_ns", [])
    risk_us: tuple = ()
    if risk:
        snap["risk_latency_ns_p99"] = _pctl(risk, 0.99)
        risk_us = tuple(v / 1000.0 for v in risk)
    else:
        notes.append("blind: no risk_latency_ns samples — latency rules skipped")
    if kill_state is None:
        try:
            from delta_os.safety import SafetyState
            kill_state = 1 if SafetyState().mode == "HALTED" else 0
        except Exception as exc:
            notes.append(f"blind: kill state unreadable ({exc}) — kill rule skipped")
            kill_state = None
    if kill_state is not None:
        snap["kill_switch_state"] = float(kill_state)
    return snap, notes, risk_us


def evaluate(snapshot: dict, risk_samples: tuple[float, ...] = ()) -> dict:
    from observability.alerts import AlertEngine
    from observability.slos import check_error_budget, check_latency_slo
    _, rules = load_alert_rules()
    engine = AlertEngine(rules)
    fired = engine.evaluate(snapshot)
    slos = []
    # Budgets follow the measured baseline (bench artifact), NOT the unmet
    # 7µs plan target — see ops_rules BASELINE NOTE. Missing data is FAIL.
    if risk_samples:
        slos.append(check_latency_slo(risk_samples, 400.0, 700.0, 900.0,
                                      name="risk-firewall-us"))
    else:
        slos.append(check_latency_slo((), 400.0, 700.0, 900.0,
                                      name="risk-firewall-us"))
    return {
        "fired": [{"rule": a.rule, "metric": a.metric, "value": a.value,
                   "severity": a.severity} for a in fired],
        "slos": [{"slo": s.slo, "status": s.status, "detail": s.detail} for s in slos],
    }


def run(workdir: Path, kill_state: int | None = None,
        metrics_json: Path | str | None = None,
        metrics_addr: str | None = None) -> dict:
    t0 = time.perf_counter()
    notes: list[str] = []
    risk_us: tuple = ()
    if metrics_json is not None:
        snap = {k: float(v) for k, v in
                json.loads(Path(metrics_json).read_text(encoding="utf-8")).items()}
        source_note = f"source: --metrics-json {metrics_json} (synthetic)"
        if kill_state is not None:
            snap["kill_switch_state"] = float(kill_state)
    else:
        addr = metrics_addr if metrics_addr is not None else os.environ.get(
            "DELTA_METRICS_ADDR", DEFAULT_METRICS_ADDR)
        try:
            snap, notes = snapshot_from_scrape(scrape_exporter(addr))
            source_note = f"source: exporter {addr}"
        except Exception as exc:
            notes = [f"blind: exporter {addr} unreachable ({exc}) — local fallback"]
            snap, local_notes, risk_us = build_snapshot(kill_state=kill_state)
            notes += local_notes
            source_note = "source: local fallback (empty telemetry)"
        else:
            if kill_state is not None:
                snap["kill_switch_state"] = float(kill_state)
            else:
                try:
                    from delta_os.safety import SafetyState
                    snap["kill_switch_state"] = 1.0 if SafetyState().mode == "HALTED" else 0.0
                except Exception as exc:
                    notes.append(f"blind: kill state unreadable ({exc}) — kill rule skipped")
    ev = evaluate(snap, tuple(risk_us))
    critical = [f for f in ev["fired"] if f["severity"] == "critical"]
    verdict = "ALERT" if critical else ("WARN" if ev["fired"] else "CLEAR")
    # P4 paging: every firing rule enters persistent escalation (report is
    # idempotent per rule+severity); due pages are listed for the operator/
    # pager to deliver. State lives beside the artifact (survives restarts).
    try:
        from observability.escalation import EscalationTracker

        tracker = EscalationTracker(Path(workdir) / "escalation.json")
        for f in ev["fired"]:
            tracker.report(str(f.get("rule", "?")), str(f.get("severity", "warning")),
                           str(f.get("reason", f.get("rule", "?"))))
        due = tracker.due_pages()
        escalation = {"open": len(tracker.open_events()),
                      "due_now": [d.event_id for d in due]}
    except Exception as exc:
        escalation = {"open": 0, "due_now": [], "error": str(exc)}
    artifact = {
        "check": "sre-wiring",
        "source_note": source_note,
        "snapshot": snap,
        "blindness_notes": notes,
        **ev,
        "verdict": verdict,
        "escalation": escalation,
        "wall_s": round(time.perf_counter() - t0, 4),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    artifact["hash"] = _sha(artifact)
    out = Path(workdir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "sre.json"
    p.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    artifact["artifact"] = str(p)
    return artifact


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="artifacts/sre")
    ap.add_argument("--kill-state", type=int, default=None)
    ap.add_argument("--metrics-json", default=None,
                    help="synthetic snapshot JSON (drills/tests); skips live sources")
    ap.add_argument("--metrics-addr", default=None,
                    help="exporter host:port (default $DELTA_METRICS_ADDR or 127.0.0.1:9108)")
    a = ap.parse_args(argv)
    r = run(Path(a.workdir), a.kill_state, a.metrics_json, a.metrics_addr)
    print(json.dumps({k: r[k] for k in ("verdict", "fired", "slos",
                                       "blindness_notes", "artifact")}, indent=2))
    for f in r["fired"]:
        print(f'REASON {f["severity"]}: {f["rule"]} — {f["metric"]}={f["value"]}')
    return 0 if r["verdict"] == "CLEAR" else 1


if __name__ == "__main__":
    raise SystemExit(main())
