from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GroundingCheck:
    claim: str
    evidence_id: str
    supported: bool
    reason: str = ""


def verify_grounding(claims: tuple[str, ...], evidence_ids: tuple[str, ...]) -> list[GroundingCheck]:
    """Local-model grounding gate: every claim must cite a supplied evidence id.

    Format: claim text must contain [evidence_id]. Unsupported claims fail.
    """
    checks: list[GroundingCheck] = []
    for claim in claims:
        cited = [e for e in evidence_ids if e in claim]
        if cited:
            checks.append(GroundingCheck(claim, cited[0], True))
        else:
            checks.append(GroundingCheck(claim, "", False, "no evidence citation"))
    return checks
