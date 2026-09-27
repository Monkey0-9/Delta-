from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class FinalCertification:

    project: str
    version: str
    timestamp: str
    python_tests: int
    rust_tests: int
    certification_hash: str
    certified: bool


def build_certification(
    *,
    python_tests: int,
    rust_tests: int,
    certification_hash: str,
    certified: bool,
) -> FinalCertification:

    if python_tests <= 0:
        raise ValueError(
            "python test evidence required"
        )

    if rust_tests <= 0:
        raise ValueError(
            "rust test evidence required"
        )

    if not certification_hash:
        raise ValueError(
            "certification hash required"
        )

    return FinalCertification(
        project="DELTA",
        version="1.0.0",
        timestamp=datetime.now(
            timezone.utc
        ).isoformat(),
        python_tests=python_tests,
        rust_tests=rust_tests,
        certification_hash=certification_hash,
        certified=certified,
    )