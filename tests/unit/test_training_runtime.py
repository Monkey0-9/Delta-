import pytest

pytest.importorskip("torch", reason="torch not installed in base CI env (ML-runtime gated)")
from finance_model.training.runtime import TrainingRuntime


def test_runtime_detects():
    runtime = TrainingRuntime.detect()

    assert runtime.device in {"cpu", "cuda"}

    if runtime.device == "cpu":
        assert runtime.bf16 is False
        assert runtime.fp16 is False