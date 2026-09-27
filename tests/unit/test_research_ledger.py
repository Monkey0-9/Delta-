from research.ledger.experiment import ExperimentSpec
from research.ledger.registry import ResearchRegistry


def make_spec() -> ExperimentSpec:
    return ExperimentSpec(
        experiment_id="EXP-TEST-001",
        hypothesis="Momentum signal contains predictive information.",
        code_commit="abc123",
        dataset_id="prices-v1",
        dataset_hash="dataset-hash",
        model_id=None,
        random_seed=42,
        universe="TEST",
        train_start="2010-01-01",
        train_end="2018-12-31",
        validation_start="2019-01-01",
        validation_end="2021-12-31",
        test_start="2022-01-01",
        test_end="2025-12-31",
        cost_model="realistic-v1",
    )


def test_experiment_fingerprint_is_deterministic():
    a = make_spec()
    b = make_spec()

    assert a.fingerprint() == b.fingerprint()


def test_registry_roundtrip(tmp_path):
    registry = ResearchRegistry(
        tmp_path / "ledger.jsonl"
    )

    spec = make_spec()

    registry.append(spec.to_dict())

    result = registry.get("EXP-TEST-001")

    assert result is not None
    assert result["experiment_id"] == "EXP-TEST-001"
    assert result["fingerprint"] == spec.fingerprint()