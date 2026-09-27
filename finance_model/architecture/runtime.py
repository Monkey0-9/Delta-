from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
import platform
import subprocess
from typing import Any

import torch
import transformers

from finance_model.inference.device import detect_device


@dataclass(frozen=True, slots=True)
class RuntimeFingerprint:
    python_version: str
    platform: str
    torch_version: str
    transformers_version: str
    cuda_version: str | None
    device: str
    device_name: str
    bf16_supported: bool
    environment_hash: str


def _git_commit() -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        commit = result.stdout.strip()

        return commit if commit else "nogit"

    except Exception:
        return "nogit"


def build_runtime_fingerprint() -> RuntimeFingerprint:
    device = detect_device()

    raw = {
        "python": device.python_version,
        "platform": platform.platform(),
        "torch": device.torch_version,
        "transformers": transformers.__version__,
        "cuda": device.cuda_version,
        "device": device.device,
        "device_name": device.device_name,
        "bf16": device.bf16_supported,
        "git": _git_commit(),
    }

    encoded = json.dumps(
        raw,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    environment_hash = hashlib.sha256(encoded).hexdigest()

    return RuntimeFingerprint(
        python_version=device.python_version,
        platform=platform.platform(),
        torch_version=device.torch_version,
        transformers_version=transformers.__version__,
        cuda_version=device.cuda_version,
        device=device.device,
        device_name=device.device_name,
        bf16_supported=device.bf16_supported,
        environment_hash=environment_hash,
    )


def runtime_metadata() -> dict[str, Any]:
    fingerprint = build_runtime_fingerprint()

    result = asdict(fingerprint)

    result["pid"] = os.getpid()
    result["git_commit"] = _git_commit()

    return result