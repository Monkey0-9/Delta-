"""DELTA OS — Institutional Readiness Auditor and Verification Engine.

Bridges the 9-dimension authoritative ReadinessEvaluator to structured CLI reports
and artifacts (artifacts/doctor/institutional_audit.json).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from delta_os.readiness import ReadinessEvaluator, ReadinessReport, CheckResult


@dataclass
class InstitutionalProbe:
    dimension: int
    name: str
    detail: str
    status: str
    latency_ms: float
    evidence: Dict[str, Any]
    mandatory: bool = True


@dataclass
class InstitutionalAuditReport:
    probes: List[InstitutionalProbe]
    overall_verdict: str
    all_mandatory_passed: bool
    live_verdict: str
    timestamp: str
    commit: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "commit": self.commit,
            "overall_verdict": self.overall_verdict,
            "all_mandatory_passed": self.all_mandatory_passed,
            "live_verdict": self.live_verdict,
            "probes": [
                {
                    "dimension": p.dimension,
                    "name": p.name,
                    "status": p.status,
                    "detail": p.detail,
                    "latency_ms": p.latency_ms,
                    "evidence": p.evidence,
                    "mandatory": p.mandatory,
                }
                for p in self.probes
            ],
        }


def run_institutional_audit(json_out: bool = False) -> InstitutionalAuditReport:
    """Execute authoritative 9-dimension audit and optionally write artifact."""
    evaluator = ReadinessEvaluator()
    rep: ReadinessReport = evaluator.evaluate()

    probes: List[InstitutionalProbe] = []
    for idx, c in enumerate(rep.checks, 1):
        probes.append(
            InstitutionalProbe(
                dimension=idx,
                name=c.dimension,
                detail=c.detail,
                status=c.status,
                latency_ms=c.latency_ms,
                evidence=c.evidence,
                mandatory=c.mandatory_for_paper,
            )
        )

    audit_report = InstitutionalAuditReport(
        probes=probes,
        overall_verdict=rep.paper_verdict,
        all_mandatory_passed=rep.paper_ready,
        live_verdict=rep.live_verdict,
        timestamp=rep.timestamp,
        commit=rep.commit,
    )

    if json_out:
        art_dir = Path("artifacts/doctor")
        art_dir.mkdir(parents=True, exist_ok=True)
        art_path = art_dir / "institutional_audit.json"
        art_path.write_text(json.dumps(audit_report.to_dict(), indent=2), encoding="utf-8")

    return audit_report
