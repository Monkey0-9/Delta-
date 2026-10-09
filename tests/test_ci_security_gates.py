"""B9: CI security gates are pinned and honest.

Pins .github/workflows/security.yml (jobs, triggers, pinned tool versions)
so the gates cannot silently rot; verifies requirements.txt covers the
heavy training imports whose absence broke quantbrain collection; runs the
real secret_scan (must be clean).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

ROOT = Path(".")
WF = ROOT / ".github" / "workflows" / "security.yml"


def _text() -> str:
    assert WF.exists(), "security workflow missing"
    return WF.read_text(encoding="utf-8")


def test_security_workflow_triggers_and_jobs():
    t = _text()
    assert "pull_request" in t and "push" in t
    for job in ("semgrep:", "bandit:", "secret-scan:", "cargo-audit:",
                "pip-audit:"):
        assert job in t, f"missing job {job}"


def test_security_workflow_pins_tool_versions():
    t = _text()
    # Unpinned scanners drift silently; every scanner must carry a version.
    assert re.search(r"semgrep==\d+\.\d+\.\d+", t), "semgrep unpinned"
    assert re.search(r"bandit==\d+\.\d+\.\d+", t), "bandit unpinned"
    assert re.search(r"cargo-audit --version \d+\.\d+\.\d+", t), "cargo-audit unpinned"
    assert re.search(r"pip-audit==\d+\.\d+\.\d+", t), "pip-audit unpinned"
    assert "actions/checkout@v4" in t and "actions/setup-python@v5" in t


def test_security_workflow_scans_repo_scopes():
    t = _text()
    # Positive list: parse the actual bandit arg list, so a dropped dir fails.
    m = re.search(r"(?m)^\s*-\s*run:\s*bandit\s+-r\s+(.+)$", t)
    assert m, "bandit run line missing"
    scopes = m.group(1).split()
    for scope in ("core", "delta_os", "execution", "governance", "risk",
                  "security", "research", "validation", "data", "simulation",
                  "broker", "observability", "scripts", "trading",
                  "finance_model"):
        assert scope in scopes, f"bandit scope missing {scope}"
    assert "requirements.txt" in t
    assert "tui/Cargo.toml" in t


def test_security_workflow_pins_fresh():
    import datetime
    t = _text()
    m = re.search(r"pins-verified:\s*(\d{4}-\d{2}-\d{2})", t)
    assert m, "pins-verified date missing from security.yml"
    age = datetime.date.today() - datetime.date.fromisoformat(m.group(1))
    assert age.days <= 180, f"scanner pins {age.days}d old — refresh versions"


def test_requirements_cover_training_imports():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dep in ("datasets", "peft", "accelerate", "pyyaml"):
        assert re.search(rf"(?m)^{dep}[>=<]", req), f"{dep} missing from requirements"
    # And the modules genuinely import (collection can no longer ModuleNotFound).
    import datasets  # noqa: F401
    import peft  # noqa: F401
    import yaml  # noqa: F401
    import accelerate  # noqa: F401


def test_secret_scan_scans_test_substring_dirs(tmp_path):
    sys.path.insert(0, "scripts")
    from release_certify import secret_scan
    d = tmp_path / "latest"
    d.mkdir()
    (d / "dummy.py").write_text('KEY = "sk-AB12CD34EF56GH78IJ90"\n',
                                encoding="utf-8")
    r = secret_scan(d)
    assert not r["ok"] and any("dummy.py" in h for h in r["hits"]), r


def test_secret_scan_skips_test_trees_by_component(tmp_path):
    sys.path.insert(0, "scripts")
    from release_certify import secret_scan
    t = tmp_path / "tests"
    t.mkdir()
    (t / "x.py").write_text('KEY = "sk-AB12CD34EF56GH78IJ90"\n',
                            encoding="utf-8")
    assert secret_scan(t)["ok"], "tests/ dir must stay skipped"
    (tmp_path / "test_unit.py").write_text('KEY = "sk-AB12CD34EF56GH78IJ90"\n',
                                           encoding="utf-8")
    (t / "keep.py").write_text("x = 1\n", encoding="utf-8")
    r = secret_scan(tmp_path)
    assert r["ok"], f"test-tree files must stay skipped: {r['hits']}"


def test_secret_scan_sk_boundary_and_json_ext(tmp_path):
    sys.path.insert(0, "scripts")
    from release_certify import secret_scan
    (tmp_path / "miss15.py").write_text('token = "sk-AB12CD34EF56GH7"\n',
                                        encoding="utf-8")
    (tmp_path / "hit20.json").write_text('{"k": "sk-AB12CD34EF56GH78IJ90"}',
                                         encoding="utf-8")
    r = secret_scan(tmp_path)
    assert any("hit20.json" in h for h in r["hits"]), r
    assert not any("miss15.py" in h for h in r["hits"]), r


def test_secret_scan_clean():
    sys.path.insert(0, "scripts")
    from release_certify import secret_scan
    r = secret_scan()
    assert r["ok"], f"secret hits: {r['hits']}"
