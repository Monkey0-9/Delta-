from __future__ import annotations

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from .contracts import ReleaseGate

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "finalization"


def command_ok(
    command: list[str],
) -> tuple[bool, str]:

    try:

        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        return (
            result.returncode == 0,
            (
                result.stdout
                + "\n"
                + result.stderr
            ).strip(),
        )

    except Exception as exc:

        return False, str(exc)


def python_tests() -> ReleaseGate:

    ok, output = command_ok(
        [
            "python",
            "-m",
            "pytest",
            "-q",
        ]
    )

    return ReleaseGate(
        name="python_tests",
        status="PASS" if ok else "FAIL",
        required=True,
        evidence=output[-4000:],
    )


def rust_tests() -> ReleaseGate:

    ok, output = command_ok(
        [
            "cargo",
            "test",
            "--workspace",
        ]
    )

    return ReleaseGate(
        name="rust_tests",
        status="PASS" if ok else "FAIL",
        required=True,
        evidence=output[-4000:],
    )


def ruff() -> ReleaseGate:

    ok, output = command_ok(
        [
            "ruff",
            "check",
            ".",
        ]
    )

    return ReleaseGate(
        name="ruff",
        status="PASS" if ok else "FAIL",
        required=True,
        evidence=output[-4000:],
    )


def research_artifacts() -> ReleaseGate:

    required = [
        ARTIFACTS / "provenance.json",
        ARTIFACTS / "dataset_manifest.json",
    ]

    missing = [
        str(path)
        for path in required
        if not path.exists()
    ]

    return ReleaseGate(
        name="research_artifacts",
        status=(
            "PASS"
            if not missing
            else "FAIL"
        ),
        required=True,
        evidence=json.dumps(
            {
                "missing": missing,
            },
            indent=2,
        ),
    )


def live_connectivity() -> ReleaseGate:

    return ReleaseGate(
        name="live_connectivity",
        status="NOT_MEASURED",
        required=False,
        evidence="No live HTTP/WS measurement supplied.",
        reason=(
            "Must not be represented as production-certified."
        ),
    )


def absolute_performance() -> ReleaseGate:

    return ReleaseGate(
        name="absolute_performance",
        status="NOT_MEASURED",
        required=False,
        evidence=(
            "No externally validated absolute latency/Sharpe "
            "target supplied."
        ),
        reason=(
            "Absolute performance claims require actual measurement."
        ),
    )


def final_gates() -> list[ReleaseGate]:

    return [
        python_tests(),
        rust_tests(),
        ruff(),
        research_artifacts(),
        live_connectivity(),
        absolute_performance(),
    ]


def production_safe(
    gates: list[ReleaseGate],
) -> bool:

    return all(
        gate.status == "PASS"
        for gate in gates
        if gate.required
    )


def write_gates() -> bool:

    gates = final_gates()

    ARTIFACTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = [
        asdict(gate)
        for gate in gates
    ]

    (ARTIFACTS / "release_gates.json").write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return production_safe(gates)
