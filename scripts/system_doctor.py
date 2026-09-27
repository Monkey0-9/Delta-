from __future__ import annotations

import importlib
import platform
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    value: str


def check_import(name: str) -> Check:
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "unknown")
        return Check(name, True, str(version))
    except Exception as exc:
        return Check(name, False, repr(exc))


def main() -> int:
    print("=" * 72)
    print("DELTA SYSTEM DOCTOR")
    print("=" * 72)

    print(f"Python       : {sys.version.split()[0]}")
    print(f"Platform     : {platform.platform()}")

    checks = [
        check_import("torch"),
        check_import("transformers"),
        check_import("trl"),
        check_import("peft"),
        check_import("datasets"),
        check_import("accelerate"),
        check_import("bitsandbytes"),
    ]

    for check in checks:
        state = "OK" if check.ok else "FAIL"
        print(f"{state:5} {check.name:16} {check.value}")

    import torch

    cuda_ok = bool(torch.cuda.is_available())

    print()
    print(f"CUDA         : {cuda_ok}")

    if cuda_ok:
        print(f"CUDA runtime  : {torch.version.cuda}")
        print(f"GPU           : {torch.cuda.get_device_name(0)}")
        print(f"Capability    : {torch.cuda.get_device_capability(0)}")
        print(f"BF16          : {torch.cuda.is_bf16_supported()}")

        props = torch.cuda.get_device_properties(0)

        print(
            f"VRAM          : "
            f"{props.total_memory / (1024 ** 3):.2f} GB"
        )

        x = torch.randn(
            1024,
            1024,
            device="cuda",
            dtype=torch.float16,
        )
        y = x @ x
        torch.cuda.synchronize()

        print(f"GPU GEMM      : OK ({tuple(y.shape)})")
        del x, y
        torch.cuda.empty_cache()
    else:
        print("GPU TEST      : FAILED")
        return 2

    print()
    print("DELTA compute environment: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
