from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def git(command: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        return result.stdout.strip()

    except Exception:
        return ""


def environment_manifest() -> dict[str, Any]:
    return {
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "implementation": platform.python_implementation(),
        "git_commit": git(
            ["rev-parse", "HEAD"]
        ),
        "git_branch": git(
            ["branch", "--show-current"]
        ),
        "git_status": git(
            ["status", "--short"]
        ),
        "git_dirty": bool(
            git(["status", "--short"])
        ),
    }


def python_packages() -> dict[str, str]:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "list",
                "--format=json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )

        packages = json.loads(
            result.stdout
        )

        return {
            item["name"]: item["version"]
            for item in packages
        }

    except Exception as exc:
        return {
            "ERROR": str(exc)
        }


def repository_hash() -> str:
    digest = hashlib.sha256()

    excluded = {
        ".git",
        ".venv",
        ".venv-delta-fm",
        "__pycache__",
        "node_modules",
        "artifacts",
    }

    files: list[Path] = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(
            part in excluded
            for part in path.parts
        ):
            continue

        files.append(path)

    for path in sorted(files):
        relative = path.relative_to(
            ROOT
        ).as_posix()

        digest.update(
            relative.encode("utf-8")
        )

        digest.update(b"\0")

        digest.update(
            sha256_file(path).encode(
                "utf-8"
            )
        )

        digest.update(b"\0")

    return digest.hexdigest()


def create_provenance() -> dict[str, Any]:
    return {
        "environment": (
            environment_manifest()
        ),
        "packages": python_packages(),
        "repository_hash": (
            repository_hash()
        ),
    }


def write_provenance(
    output: Path,
) -> None:
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = create_provenance()

    output.write_text(
        json.dumps(
            data,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def create_experiment_registry() -> list[
    dict[str, Any]
]:
    return [
        {
            "id": "W84_BASELINES",
            "hypothesis": (
                "DELTA should be evaluated "
                "against non-agentic classical "
                "strategies."
            ),
            "type": "baseline",
        },
        {
            "id": "W85_DELTA_STATIC",
            "hypothesis": (
                "The complete DELTA decision "
                "stack provides measurable "
                "differences relative to "
                "simple baselines."
            ),
            "type": "system",
        },
        {
            "id": "W86_FAILURE_LEARNING",
            "hypothesis": (
                "Failure-attributed adaptation "
                "changes out-of-sample behavior."
            ),
            "type": "ablation",
        },
        {
            "id": "W87_REGIME",
            "hypothesis": (
                "Explicit regime information "
                "changes strategy behavior "
                "under non-stationarity."
            ),
            "type": "ablation",
        },
        {
            "id": "W88_UNCERTAINTY",
            "hypothesis": (
                "Uncertainty-aware decisions "
                "alter risk-adjusted outcomes."
            ),
            "type": "ablation",
        },
        {
            "id": "W89_DIGITAL_TWIN",
            "hypothesis": (
                "Scenario evaluation changes "
                "candidate-action selection."
            ),
            "type": "ablation",
        },
        {
            "id": "W90_MEMORY",
            "hypothesis": (
                "Experience memory changes "
                "subsequent decisions after "
                "attributed failures."
            ),
            "type": "ablation",
        },
        {
            "id": "W91_AGENTS",
            "hypothesis": (
                "Multi-agent research provides "
                "incremental information beyond "
                "individual research channels."
            ),
            "type": "ablation",
        },
        {
            "id": "W92_NATIVE",
            "hypothesis": (
                "Native kernels improve measured "
                "compute performance for selected "
                "workloads."
            ),
            "type": "benchmark",
        },
        {
            "id": "W93_PARITY",
            "hypothesis": (
                "Native implementations are "
                "numerically equivalent within "
                "predefined tolerance."
            ),
            "type": "correctness",
        },
        {
            "id": "W94_LATENCY",
            "hypothesis": (
                "End-to-end latency can be "
                "characterized reproducibly "
                "under controlled local conditions."
            ),
            "type": "benchmark",
        },
        {
            "id": "W95_NETWORK",
            "hypothesis": (
                "Network/API overhead can be "
                "separately measured from local "
                "decision latency."
            ),
            "type": "benchmark",
        },
        {
            "id": "W96_GPU",
            "hypothesis": (
                "GPU acceleration has a measurable "
                "crossover point for simulation "
                "workloads."
            ),
            "type": "benchmark",
        },
        {
            "id": "W97_STATISTICS",
            "hypothesis": (
                "Observed strategy differences "
                "survive appropriate statistical "
                "validation."
            ),
            "type": "statistics",
        },
        {
            "id": "W98_STRESS",
            "hypothesis": (
                "The system remains bounded under "
                "predefined adverse scenarios."
            ),
            "type": "stress",
        },
    ]
