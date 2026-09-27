from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ComputeBackend(StrEnum):
    CPU = "cpu"
    CUDA = "cuda"


@dataclass(frozen=True, slots=True)
class ComputeCapability:
    backend: ComputeBackend
    available: bool
    device_name: str | None = None


def detect_cuda() -> ComputeCapability:
    """
    Honest CUDA capability probe: reports CUDA only when a torch
    installation actually exposes a GPU. Otherwise CPU. Never claims
    acceleration without a measurable device behind it.
    """
    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            return ComputeCapability(
                backend=ComputeBackend.CUDA,
                available=True,
                device_name=torch.cuda.get_device_name(0),
            )
    except Exception:
        pass
    return ComputeCapability(
        backend=ComputeBackend.CPU,
        available=True,
        device_name=None,
    )


def select_backend(prefer_gpu: bool = True) -> ComputeCapability:
    """CPU unless a real CUDA device is present and preferred."""
    cuda = detect_cuda()
    if prefer_gpu and cuda.backend is ComputeBackend.CUDA and cuda.available:
        return cuda
    return ComputeCapability(
        backend=ComputeBackend.CPU,
        available=True,
        device_name=None,
    )
