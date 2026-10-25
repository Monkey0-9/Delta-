"""Acceptance tests for DELTA Authoritative Readiness & Institutional Doctor.

Verifies:
1. Authoritative 9-dimension probes run dynamically without hardcoded mocks.
2. Structured output includes latency, evidence, and distinct paper/live verdicts.
3. Live trading remains strictly FAIL-CLOSED BLOCKED.
4. delta doctor --institutional exits 0 when paper gates pass.
5. delta doctor --institutional exits 1 when a mandatory gate fails.
6. delta doctor --institutional --json produces artifacts/doctor/institutional_audit.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner
import pytest

from apps.cli.main import app
from delta_os.readiness import ReadinessEvaluator, CheckResult

runner = CliRunner()


def test_readiness_evaluator_live_audit():
    evaluator = ReadinessEvaluator()
    report = evaluator.evaluate()

    assert len(report.checks) == 9
    dims = [c.dimension for c in report.checks]
    assert "Native C-ABI Kernel" in dims
    assert "Temporal PIT Data" in dims
    assert "Canonical OMS Journal" in dims
    assert "Sentinel 24/7 Daemon" in dims
    assert "Quantitative Models" in dims
    assert "Broker Adapters" in dims
    assert "Risk Firewall & Auth" in dims
    assert "Network Protocol Bridge" in dims
    assert "Release Gate State" in dims

    # Paper verdict should be pass on fresh environment
    assert report.paper_ready is True
    assert "GO-PAPER" in report.paper_verdict

    # Live trading must ALWAYS be blocked fail-closed
    assert report.live_ready is False
    assert "FAIL-CLOSED BLOCKED" in report.live_verdict


def test_doctor_institutional_cli_output():
    res = runner.invoke(app, ["doctor", "--institutional"])
    assert res.exit_code == 0
    assert "INSTITUTIONAL QUANTITATIVE AUDIT & READINESS REPORT" in res.stdout
    assert "Native C-ABI Kernel" in res.stdout
    assert "Temporal PIT Data" in res.stdout
    assert "Canonical OMS Journal" in res.stdout
    assert "VERDICT: GO-PAPER / INSTITUTIONAL_AUDIT_PASS" in res.stdout


def test_doctor_institutional_json_output(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Ensure SYSTEM_STATUS.yaml exists in tmp_path
    sys_status = Path(__file__).resolve().parents[1] / "SYSTEM_STATUS.yaml"
    (tmp_path / "SYSTEM_STATUS.yaml").write_text(sys_status.read_text())

    res = runner.invoke(app, ["doctor", "--institutional", "--json"])
    assert res.exit_code == 0
    data = json.loads(res.stdout)
    assert data["all_mandatory_passed"] is True
    assert "GO-PAPER" in data["overall_verdict"]
    assert "FAIL-CLOSED" in data["live_verdict"]
    assert len(data["probes"]) == 9

    art = tmp_path / "artifacts" / "doctor" / "institutional_audit.json"
    assert art.exists()
    saved = json.loads(art.read_text())
    assert saved["commit"] == data["commit"]


def test_readiness_evaluator_mandatory_failure_causes_exit_code_1(monkeypatch):
    # Mock a critical native kernel failure
    def mock_fail_native(self):
        return CheckResult(
            dimension="Native C-ABI Kernel",
            status="FAIL",
            detail="FAILED: SIMD instruction bus error",
            latency_ms=1.0,
            evidence={"error": "bus error"},
            mandatory_for_paper=True,
        )

    monkeypatch.setattr(ReadinessEvaluator, "_probe_native_kernel", mock_fail_native)

    evaluator = ReadinessEvaluator()
    report = evaluator.evaluate()
    assert report.paper_ready is False
    assert "NO-GO-PAPER" in report.paper_verdict

    res = runner.invoke(app, ["doctor", "--institutional"])
    assert res.exit_code == 1
    assert "NO-GO-PAPER" in res.stdout
