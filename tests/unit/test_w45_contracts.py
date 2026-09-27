"""W45 contracts: deterministic ResearchSpec -> ExperimentSpec, PIT rule, ledger lookup."""
from research.contracts import ResearchSpec
from research.ledger.experiment import ExperimentSpec
from research.ledger.registry import ResearchRegistry


def test_research_spec_windows_split_chronologically():
    spec = ResearchSpec(asset_universe="SP500", strategy="momentum", start="2015-01-01", end="2025-12-31")
    w = spec.train_val_test_windows()
    assert w["train_start"] == "2015-01-01"
    assert w["train_end"] <= w["validation_end"] <= w["test_end"] == "2025-12-31"
    assert spec.experiment_id() == spec.experiment_id()  # deterministic


def test_research_spec_rejects_bad_contracts():
    import pytest

    with pytest.raises(ValueError):
        ResearchSpec(asset_universe="NOPE", strategy="momentum", start="2015-01-01", end="2025-12-31")
    with pytest.raises(ValueError):
        ResearchSpec(asset_universe="SP500", strategy="momentum", start="2025-12-31", end="2015-01-01")


def test_experiment_kwargs_build_valid_spec():
    spec = ResearchSpec(asset_universe="SP500", strategy="momentum", start="2015-01-01", end="2025-12-31")
    kwargs = spec.to_experiment_kwargs(code_commit="abc123", dataset_id="sp500-pit-v1", dataset_hash="h")
    exp = ExperimentSpec(**kwargs)
    assert exp.fingerprint() == exp.fingerprint()
    manifest = spec.manifest()
    assert manifest["schema"] == "delta.research_manifest.v1"
    assert manifest["pit_contract"]["rule"].startswith("research may only see")


def test_registry_get_finds_nested_runner_rows(tmp_path):
    reg = ResearchRegistry(tmp_path / "ledger.jsonl")
    reg.append({"type": "experiment_result", "experiment": {"experiment_id": "EXP-ABC123"}, "result": {}})
    assert reg.get("EXP-ABC123") is not None
