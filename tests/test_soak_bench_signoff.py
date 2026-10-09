"""B10: soak/bench/sign-off harness pins.

Soak runs bounded cycles clean with kill flaps + journal replays; bench
measures this box honestly (targets may FAIL — the pin is that results are
real, hashed, and machine-labeled); sign-off renders GO-PAPER/NO-GO-LIVE
from fixture artifacts and never auto-approves LIVE.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")


def _hash_ok(p: Path) -> bool:
    payload = json.loads(p.read_text(encoding="utf-8"))
    h = payload.pop("hash")
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest() == h


def test_soak_bounded_pass_and_honest_scope(tmp_path):
    from soak_shadow import run
    r = run(tmp_path, cycles=20, flap_every=5, replay_every=10)
    assert r["verdict"] == "PASS", r
    assert r["orders"] == r["fills"] == 20
    assert r["reconcile_mismatches"] == 0 and r["errors"] == 0
    assert r["kill_flaps"] == 3 and r["journal_replays"] == 2
    assert "14-day" in r["scope_note"]
    assert _hash_ok(Path(r["artifact"]))


def test_soak_kill_flap_blocks_mid_run(tmp_path):
    from soak_shadow import run
    # flap_every=1 stresses the panic path every cycle; still clean.
    r = run(tmp_path, cycles=5, flap_every=1, replay_every=5)
    assert r["verdict"] == "PASS" and r["kill_flaps"] == 4


def test_bench_measures_this_box_honestly(tmp_path):
    from bench_certify import run
    r = run(tmp_path, n_firewall=200, n_journal=200, n_gateway=50, n_lob=2000)
    assert r["machine"]["python"]
    assert r["machine"]["cpu_count"] >= 1
    fw = r["components"]["firewall_check"]
    assert fw["n"] == 200 and fw["p50_us"] > 0 and fw["p99_us"] >= fw["p50_us"]
    assert fw["verdict"] in ("PASS", "FAIL")  # measured truth, either way
    lob = r["components"]["native_lob"]
    assert lob["verdict"] in ("PASS", "FAIL", "UNMEASURED")
    if lob["verdict"] != "UNMEASURED":
        assert lob["ops_per_s"] > 0
    assert "isolated hardware" in r["scope_note"]
    assert _hash_ok(Path(r["artifact"]))


def _fixture_tree(tmp_path: Path, bench_verdict="PASS", sre_verdict="CLEAR",
                  release_status="PASS", signatures=None) -> Path:
    root = tmp_path / "proj"
    (root / "artifacts" / "release").mkdir(parents=True)
    for rel in ("TEST_CERTIFICATION", "DATA_CERTIFICATION", "RISK_CERTIFICATION",
                "OMS_CERTIFICATION", "BROKER_CERTIFICATION",
                "KILLSWITCH_CERTIFICATION", "RECONCILIATION_CERTIFICATION",
                "SECURITY_CERTIFICATION", "OBSERVABILITY_CERTIFICATION",
                "RECOVERY_CERTIFICATION"):
        payload = {"gate": rel, "status": release_status}
        payload["hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        (root / "artifacts" / "release" / f"{rel}.json").write_text(json.dumps(payload))
    for sub, name, verdict in (("dr", "drill", bench_verdict), ("sre", "sre", sre_verdict),
                               ("soak", "soak", "PASS"), ("bench", "bench", bench_verdict)):
        d = root / "artifacts" / sub
        d.mkdir(parents=True, exist_ok=True)
        payload = {"verdict": verdict}
        if sub == "bench":
            payload.update({"blockers": [], "unmeasured": []})
        payload["hash"] = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        (d / f"{name}.json").write_text(json.dumps(payload))
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "security.yml").write_text(
        "semgrep:\nbandit:\nsecret-scan:\ncargo-audit:\n")
    if signatures:
        (root / "artifacts" / "signoff").mkdir(parents=True, exist_ok=True)
        (root / "artifacts" / "signoff" / "signatures.json").write_text(
            json.dumps(signatures))
    return root


def test_signoff_all_green_without_signatures_is_paper_only(tmp_path):
    from signoff import run
    m = run(_fixture_tree(tmp_path))
    assert all(r["sign_off"] == "APPROVED" for r in m["rows"])
    assert m["paper"] == "GO-PAPER" and m["live"] == "NO-GO-LIVE"
    assert len(m["missing_signatures"]) == 5
    md = (tmp_path / "proj" / "artifacts" / "signoff" / "matrix.md").read_text()
    assert "NO-GO-LIVE" in md and "GO-PAPER" in md


def test_signoff_blockers_hold_rows_and_paper(tmp_path):
    from signoff import run
    m = run(_fixture_tree(tmp_path, bench_verdict="FAIL", release_status="FAIL"))
    by = {r["stakeholder"]: r for r in m["rows"]}
    assert by["Head of Engineering"]["sign_off"] == "HOLD"
    assert by["Head of Quantitative"]["sign_off"] == "HOLD"
    assert m["paper"] == "NO-GO-PAPER" and m["live"] == "NO-GO-LIVE"


def test_signoff_missing_artifact_holds_loudly(tmp_path):
    from signoff import run
    root = _fixture_tree(tmp_path)
    (root / "artifacts" / "dr" / "drill.json").unlink()
    m = run(root)
    by = {r["stakeholder"]: r for r in m["rows"]}
    assert by["Head of Engineering"]["sign_off"] == "HOLD"
    assert any("missing artifact" in reason for reason in by["Head of Engineering"]["reasons"])
    assert m["live"] == "NO-GO-LIVE"


def test_signoff_tampered_artifact_holds(tmp_path):
    from signoff import run
    root = _fixture_tree(tmp_path)
    p = root / "artifacts" / "soak" / "soak.json"
    payload = json.loads(p.read_text())
    payload["verdict"] = "PASS"
    payload["hash"] = "deadbeef"  # tampered envelope
    p.write_text(json.dumps(payload))
    m = run(root)
    by = {r["stakeholder"]: r for r in m["rows"]}
    assert by["Head of Operations"]["sign_off"] == "HOLD"
    assert any("HASH MISMATCH" in reason for reason in by["Head of Operations"]["reasons"])


def test_soak_shadow_never_submits_live_and_emits_incomplete(tmp_path):
    from soak_shadow import run, verify_no_live_submit_path
    assert verify_no_live_submit_path()["live_submit_paths"] == 0
    r = run(tmp_path, cycles=5, flap_every=5, replay_every=5)
    assert r["broker_submits"] == 0
    assert r["hypothetical_fills"] == 5
    assert r["mirror_diffs"] == 0
    assert r["status"] == "INCOMPLETE" and r["soak_complete"] is False
    assert r["verdict"] == "PASS"  # bounded cycles clean, wall-clock still open
    assert "never claims SOAK_COMPLETE" in r["scope_note"]


def test_bench_unmeasured_kernels_are_unavailable_and_stamped(tmp_path):
    from bench_certify import run
    r = run(tmp_path, n_firewall=50, n_journal=50, n_gateway=10, n_lob=500)
    comps = r["components"]
    for k in ("lob_insert", "lob_cancel", "lob_replace", "lob_match",
              "dedup", "serialization"):
        assert comps[k]["verdict"] == "UNAVAILABLE", k
        assert "no number claimed" in comps[k]["reason"]
    fw = comps["firewall_check"]
    assert fw["p99_9_us"] >= fw["p99_us"] > 0 and fw["measured_utc"]
    assert r["machine"]["measured_utc"] and "ram_gb" in r["machine"]
    assert comps["native_lob"]["verdict"] in ("FAIL", "UNMEASURED")
    assert comps["firewall_check"]["verdict"] == "FAIL"  # ~300µs p99 vs 7µs target


def test_signoff_empty_tree_defaults_no_go(tmp_path):
    from signoff import run
    root = tmp_path / "empty"
    root.mkdir()
    m = run(root)
    assert m["paper"] == "NO-GO-PAPER" and m["live"] == "NO-GO-LIVE"
    assert m["live_blockers"]  # explicit blockers, never a bare verdict
    assert any("SYSTEM_STATUS" in b for b in m["live_blockers"])
    md = (root / "artifacts" / "signoff" / "matrix.md").read_text()
    assert "NO-GO-LIVE" in md and "Live blockers" in md
