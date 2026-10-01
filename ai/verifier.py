"""Claim verifier (Phase 2).

Tests whether referenced evidence actually supports a claim — never
whether a citation token merely exists. Scope is honest and narrow:
numeric assertions against evidence payload numbers (with tolerance),
temporal validity (availability vs decision time), and staleness.
Anything outside this scope reports UNSUPPORTED, never SUPPORTED.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from ai.contracts import Claim, ClaimVerdict, Evidence


@dataclass(frozen=True, slots=True)
class VerificationOutcome:
    claim_id: str
    verdict: ClaimVerdict
    detail: str
    checked_refs: tuple[str, ...] = ()


def _payload_number(payload: Mapping[str, Any], path: str) -> float | None:
    cur: Any = payload
    for part in path.split("."):
        if isinstance(cur, Mapping) and part in cur:
            cur = cur[part]
        else:
            return None
    return float(cur) if isinstance(cur, (int, float)) else None


class ClaimVerifier:
    """Verifies claims against an evidence store."""

    def __init__(self, store: Mapping[str, Evidence],
                 stale_after_s: float = 3600.0) -> None:
        self._store = dict(store)
        self._stale_after_s = stale_after_s

    def verify(self, claim: Claim,
               now: datetime | None = None) -> VerificationOutcome:
        at = now or datetime.now(timezone.utc)
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        if not claim.evidence_refs:
            return VerificationOutcome(claim.claim_id, ClaimVerdict.UNSUPPORTED,
                                       "no evidence refs", ())
        missing = [r for r in claim.evidence_refs if r not in self._store]
        if missing:
            return VerificationOutcome(claim.claim_id, ClaimVerdict.UNSUPPORTED,
                                       f"missing evidence: {missing}",
                                       tuple(claim.evidence_refs))
        # Temporal validity: evidence must have been available at decision time.
        if claim.decision_at is not None:
            dec = claim.decision_at
            if dec.tzinfo is None:
                dec = dec.replace(tzinfo=timezone.utc)
            for ref in claim.evidence_refs:
                ev = self._store[ref]
                if ev.available_at is not None:
                    avl = ev.available_at
                    if avl.tzinfo is None:
                        avl = avl.replace(tzinfo=timezone.utc)
                    if avl > dec:
                        return VerificationOutcome(
                            claim.claim_id, ClaimVerdict.TEMPORALLY_INVALID,
                            f"{ref} available {avl.isoformat()} after decision "
                            f"{dec.isoformat()}", tuple(claim.evidence_refs))
        # Staleness.
        for ref in claim.evidence_refs:
            ev = self._store[ref]
            age = (at - ev.retrieved_at).total_seconds()
            if age > self._stale_after_s:
                return VerificationOutcome(claim.claim_id, ClaimVerdict.STALE,
                                           f"{ref} age {age:.0f}s exceeds "
                                           f"{self._stale_after_s:.0f}s",
                                           tuple(claim.evidence_refs))
        # Numeric assertions: every (path, expected, tol) must hold in at
        # least one referenced evidence payload; contradictions fail.
        if claim.numeric_assertions:
            for path, expected, tol in claim.numeric_assertions:
                matched, contradicted = False, False
                for ref in claim.evidence_refs:
                    got = _payload_number(self._store[ref].payload, path)
                    if got is None:
                        continue
                    if abs(got - expected) <= tol:
                        matched = True
                    else:
                        contradicted = True
                if contradicted and not matched:
                    return VerificationOutcome(
                        claim.claim_id, ClaimVerdict.CONTRADICTED,
                        f"{path}: no evidence within {tol} of {expected}",
                        tuple(claim.evidence_refs))
                if not matched:
                    return VerificationOutcome(
                        claim.claim_id, ClaimVerdict.UNSUPPORTED,
                        f"{path}: no evidence carries this field",
                        tuple(claim.evidence_refs))
            return VerificationOutcome(claim.claim_id, ClaimVerdict.SUPPORTED,
                                       "all numeric assertions entailed",
                                       tuple(claim.evidence_refs))
        # No checkable assertions: citation presence alone never SUPPORTS.
        return VerificationOutcome(claim.claim_id, ClaimVerdict.UNSUPPORTED,
                                   "no verifiable assertions; citation != support",
                                   tuple(claim.evidence_refs))


__all__ = ["ClaimVerifier", "VerificationOutcome"]
