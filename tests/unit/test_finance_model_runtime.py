import pytest

torch = pytest.importorskip("torch", reason="torch not installed in base CI env (ML-runtime gated)")
from finance_model.architecture.runtime import (
    build_runtime_fingerprint,
)
from finance_model.inference.device import (
    detect_device,
)


def test_runtime_fingerprint_exists():

    runtime = build_runtime_fingerprint()

    assert runtime.python_version
    assert runtime.torch_version
    assert runtime.device
    assert runtime.environment_hash
    assert len(runtime.environment_hash) == 64


def test_device_detection():

    info = detect_device()

    assert info.device in {
        "cpu",
        "cuda",
    }

    assert info.torch_version