"""Stage-1 quality gate (plan D): FAIL datasets never enter training/promotion.

Maps DataQualityChecker overall_quality → PASS/WARN/FAIL verdict and raises
fail-closed with reason logged. Quarantine path included.
"""
from __future__ import annotations

from dataclasses import dataclass


class QualityGateBlocked(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    symbol: str
    verdict: str  # PASS|WARN|FAIL
    overall_quality: str
    reason: str = ""
    quarantined: bool = False


_VERDICT = {
    "EXCELLENT": "PASS",
    "GOOD": "PASS",
    "ACCEPTABLE": "WARN",
    "POOR": "FAIL",
    "UNUSABLE": "FAIL",
}


def verdict_for(overall_quality: str) -> str:
    return _VERDICT.get((overall_quality or "").upper(), "FAIL")


def gate_report(symbol: str, overall_quality: str, reason: str = "") -> DataQualityReport:
    v = verdict_for(overall_quality)
    return DataQualityReport(symbol=symbol, verdict=v, overall_quality=overall_quality,
                             reason=reason, quarantined=(v == "FAIL"))


def assert_quality_or_raise(report: DataQualityReport) -> None:
    if report.verdict == "FAIL":
        raise QualityGateBlocked(
            f"quality gate FAIL for {report.symbol} "
            f"({report.overall_quality}): {report.reason} — quarantined, "
            f"training/promotion refused")
