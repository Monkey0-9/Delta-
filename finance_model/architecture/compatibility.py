from __future__ import annotations

from dataclasses import dataclass

from .runtime_spec import Precision, RuntimeSpec


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    device: str
    total_memory_bytes: int
    compute_capability: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    compatible: bool
    reasons: tuple[str, ...]


def validate_runtime(
    spec: RuntimeSpec,
    device: DeviceProfile,
) -> CompatibilityResult:
    reasons: list[str] = []

    if device.device.startswith("cuda"):
        major, minor = device.compute_capability or (0, 0)

        if (major, minor) < (8, 0):
            reasons.append(
                "CUDA compute capability below DELTA minimum 8.0"
            )

        if spec.precision == Precision.BF16 and (major, minor) < (8, 0):
            reasons.append(
                "BF16 requested on unsupported accelerator"
            )

    if spec.max_sequence_length > 8192:
        reasons.append(
            "Sequence length above local DELTA development limit"
        )

    return CompatibilityResult(
        compatible=not reasons,
        reasons=tuple(reasons),
    )