"""P0-2 tests: grounded staged dataset integrity + oracle correctness."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

DATA = Path("data/finance_grounded/delta_finance_grounded.jsonl")
MAN = Path("data/finance_grounded/manifest.json")


def _rows():
    return [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_grounded_schema_and_labels():
    rows = _rows()
    assert len(rows) >= 170
    for r in rows:
        assert set(("instruction", "input", "output", "source", "stage", "synthetic")) <= set(r)
        assert r["output"].strip() and r["source"].strip()
        assert r["stage"] in ("S1_domain", "S2_numerical", "S3_refusal")
        assert r["synthetic"] is True  # never presented as live market truth


def test_manifest_matches_file():
    m = json.loads(MAN.read_text(encoding="utf-8"))
    assert m["rows"] == len(_rows())
    assert m["sha256"] == hashlib.sha256(DATA.read_bytes()).hexdigest()
    assert m["live_numbers"] is False
    assert set(m["stages"]) == {"S1_domain", "S2_numerical", "S3_refusal"}


def test_s2_oracles_match_closed_forms():
    rows = [r for r in _rows() if r["stage"] == "S2_numerical"]
    by_src = {}
    for r in rows:
        by_src.setdefault(r["source"], []).append(r["output"])
    # Simple return 105/100-1 = 0.05 exactly as formatted.
    assert any("0.050000" in o for o in by_src["oracle:simple_return"])
    # Kelly (0.55*1-0.45)/1 = 0.10.
    assert any("0.1000" in o for o in by_src["oracle:kelly"])
    # Drawdown on [100,110,105,95,102]: peak 110 -> trough 95 = 15/110.
    assert any("0.136364" in o for o in by_src["oracle:drawdown"])
    # Bond price must be recomputed identically here (oracle parity).
    px = sum(5.0 / 1.04 ** t for t in (1, 2, 3)) + 100.0 / 1.04 ** 3
    assert any(f"{px:.4f}" in o for o in by_src["oracle:bond_price"])
    # VaR/CVaR rows carry the deterministic-calculator tag.
    assert all("deterministic calculator" in o for o in by_src["oracle:var_cvar"])


def test_s3_refusals_fail_closed():
    rows = [r for r in _rows() if r["stage"] == "S3_refusal"]
    assert len(rows) >= 40
    assert any("NO_TRADE" in r["output"] for r in rows)
    assert any("ABSTAIN" in r["output"] for r in rows)
    # No refusal row may promise execution or certainty.
    for r in rows:
        lo = r["output"].lower()
        assert "guaranteed" not in lo and "will go to $" not in lo
