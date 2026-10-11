"""§6: capability register schema + cross-doc agreement."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
LADDER = ["designed", "implemented", "tested", "validated",
          "paper", "shadow", "production"]
REQUIRED = ["id", "canonical_impl", "integration_path", "tests", "evidence",
            "performance", "known_limitations", "release_status",
            "owner", "blocker"]


def _register():
    with open(REPO / "docs" / "CAPABILITY_REGISTER.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_register_schema_valid():
    reg = _register()
    assert reg["status_ladder"] == LADDER
    ids = [c["id"] for c in reg["capabilities"]]
    assert len(ids) == len(set(ids)), "duplicate capability IDs"
    for cap in reg["capabilities"]:
        for field in REQUIRED:
            assert field in cap, f"{cap.get('id')}: missing {field}"
        assert cap["release_status"] in LADDER, cap["id"]
        assert isinstance(cap["tests"], list) and cap["tests"], cap["id"]
        assert isinstance(cap["known_limitations"], list), cap["id"]


def test_register_evidence_tests_exist():
    reg = _register()
    missing = []
    for cap in reg["capabilities"]:
        for t in cap["tests"]:
            target = t.split("::")[0]
            candidate = REPO / target
            if not candidate.exists():
                # Rust tests live under tui/ and are verified by cargo.
                if not str(target).startswith("tui/"):
                    missing.append(f"{cap['id']}: {t}")
    assert not missing, missing


def test_no_production_claim_without_gates():
    reg = _register()
    for cap in reg["capabilities"]:
        assert cap["release_status"] != "production", (
            f"{cap['id']}: production requires §8 gates + sign-offs")
