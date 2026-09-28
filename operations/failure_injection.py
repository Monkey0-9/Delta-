"""W231-W250 (M+N) — Failure injection (proves fail-safe) + secrets architecture.

Faults: feed loss, db loss, network partition, broker disconnect, clock skew,
duplicate/out-of-order/corrupted/stale packets, model + risk-service failure.
Secrets: Vault -> short-lived credential -> adapter -> gateway. Never
.env/config.yaml/source/Git for production secrets.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

FAULTS: tuple[str, ...] = ("feed_loss", "db_loss", "net_partition", "broker_disconnect",
                           "clock_skew", "duplicate", "out_of_order", "corrupted",
                           "stale", "model_failure", "risk_service_failure")


@dataclass
class FaultResult:
    fault: str
    failed_safe: bool
    state_intact: bool
    detail: str


class FailureInjector:
    """Runs each fault against a system stub; verifies fail-closed behavior."""

    def inject(self, system) -> list[FaultResult]:
        out: list[FaultResult] = []
        for f in FAULTS:
            try:
                res = system.handle_fault(f)
                ok = bool(res.get("failed_safe", False))
                intact = bool(res.get("state_intact", False))
                out.append(FaultResult(f, ok, intact, res.get("detail", "")))
            except Exception as e:  # noqa: BLE001 - a raise across the boundary IS the failure
                out.append(FaultResult(f, False, False, f"exception escaped: {e}"))
        return out

    def all_safe(self, results: list[FaultResult]) -> bool:
        return all(r.failed_safe and r.state_intact for r in results)


class FailSafeStub:
    """Reference system: halts trading, preserves ledger, on every fault."""

    def __init__(self) -> None:
        self.trading_halted = False
        self.ledger: list[str] = ["genesis"]

    def handle_fault(self, fault: str) -> dict:
        self.trading_halted = True  # fail-closed: stop, don't guess
        self.ledger.append(fault)
        return {"failed_safe": True, "state_intact": True,
                "detail": f"halted on {fault}, ledger={len(self.ledger)}"}


# ---------- secrets ----------

@dataclass(frozen=True, slots=True)
class ShortLivedCredential:
    token_hash: str
    scope: str
    expires_at: int  # unix seconds
    broker: str


class SecretVault:
    """Test-double vault: mints scoped short-lived credentials; tracks provenance."""

    def __init__(self, now: int = 1_700_000_000) -> None:
        self._now = now
        self._issued: list[ShortLivedCredential] = []

    def mint(self, scope: str, broker: str, ttl_s: int = 900) -> ShortLivedCredential:
        raw = f"{scope}:{broker}:{self._now}:{len(self._issued)}"
        tok = ShortLivedCredential(hashlib.sha256(raw.encode()).hexdigest()[:16],
                                   scope, self._now + ttl_s, broker)
        self._issued.append(tok)
        return tok

    def valid(self, cred: ShortLivedCredential) -> bool:
        return cred.expires_at > self._now


FORBIDDEN_SECRET_PATHS: tuple[str, ...] = (".env", "config.yaml", "source code", "git")


def audit_secret_path(path: str) -> tuple[bool, str]:
    lowered = path.lower()
    for fp in FORBIDDEN_SECRET_PATHS:
        if fp in lowered:
            return False, f"production secret must never live in {fp}"
    return True, "path acceptable (vault-backed)"
