from __future__ import annotations

from dataclasses import dataclass
import platform
import sys

import torch


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    device: str
    device_type: str
    device_name: str
    cuda_available: bool
    cuda_version: str | None
    torch_version: str
    python_version: str
    bf16_supported: bool
    total_vram_bytes: int | None


def detect_device() -> DeviceInfo:
    cuda_available = bool(torch.cuda.is_available())

    if cuda_available:
        device = "cuda"
        device_type = "cuda"
        device_name = torch.cuda.get_device_name(0)

        cuda_version = torch.version.cuda

        bf16_supported = bool(
            hasattr(torch.cuda, "is_bf16_supported")
            and torch.cuda.is_bf16_supported()
        )

        total_vram_bytes = int(
            torch.cuda.get_device_properties(0).total_memory
        )

    else:
        device = "cpu"
        device_type = "cpu"
        device_name = platform.processor() or "CPU"
        cuda_version = None
        bf16_supported = False
        total_vram_bytes = None

    return DeviceInfo(
        device=device,
        device_type=device_type,
        device_name=device_name,
        cuda_available=cuda_available,
        cuda_version=cuda_version,
        torch_version=torch.__version__,
        python_version=sys.version.split()[0],
        bf16_supported=bf16_supported,
        total_vram_bytes=total_vram_bytes,
    )


def select_dtype(
    *,
    prefer_bf16: bool = True,
) -> torch.dtype:
    info = detect_device()

    if info.cuda_available and prefer_bf16 and info.bf16_supported:
        return torch.bfloat16

    if info.cuda_available:
        return torch.float16

    return torch.float32