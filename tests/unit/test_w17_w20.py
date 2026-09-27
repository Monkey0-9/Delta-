from benchmark.gpu_contract import (
    ComputeBackend,
    detect_cuda,
)
from benchmark.workloads import benchmark


def test_benchmark_is_deterministic_in_result() -> None:
    result = benchmark(
        name="constant",
        function=lambda: "DELTA",
        iterations=5,
    )

    assert result.name == "constant"
    assert result.iterations == 5
    assert result.result_digest == "DELTA"
    assert result.operations_per_second > 0


def test_cuda_contract_is_safe_by_default() -> None:
    capability = detect_cuda()

    try:
        import torch  # type: ignore

        cuda_present = bool(torch.cuda.is_available())
    except Exception:
        cuda_present = False

    if cuda_present:
        assert capability.backend == ComputeBackend.CUDA
        assert capability.available is True
    else:
        # Honest contract: CPU, never a phantom GPU.
        assert capability.available is True
        assert capability.device_name is None
