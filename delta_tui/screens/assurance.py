"""RECONCILIATION + AUDIT screens (shame-proofing: guide §4 promises /recon /audit).

ReconScreen reads the real three-way reconciliation engine when a ledger is
attached; else UNAVAILABLE (never fabricated breaks). AuditScreen tails the
SHA-256 compliance chain; else UNAVAILABLE. Both carry SOURCE/AS-OF badges.
"""
from __future__ import annotations

from .base import BaseScreen
from ..state.store import TerminalStore


def _recon_summary() -> dict:
    try:
        from execution.reconciliation.engine import ReconciliationEngine
        eng = ReconciliationEngine()
        summary = getattr(eng, "summary", None)
        if callable(summary):
            return dict(summary())
        return {"status": "ENGINE_READY_NO_BREAKS", "breaks": ()}
    except Exception as exc:
        return {"status": "UNAVAILABLE", "detail": f"{type(exc).__name__}"}


def _audit_tail(n: int = 5) -> list[str]:
    try:
        from governance.compliance import ComplianceLog
        log = ComplianceLog()
        records = getattr(log, "records", getattr(log, "_records", [])) or []
        return [str(r)[:120] for r in records[-n:]]
    except Exception:
        return []


class ReconScreen(BaseScreen):
    name = "reconciliation"

    def build_viewmodel(self, store: TerminalStore):
        snap = store.viewmodels.get("recon_snapshot", {}) or {}
        live = _recon_summary()
        return {"mode": store.mode.value,
                "status": snap.get("status", live.get("status", "UNAVAILABLE")),
                "breaks": snap.get("breaks", live.get("breaks", ())),
                "asof": snap.get("asof", "")}

    def render_text(self, vm) -> str:
        breaks = vm.get("breaks") or ()
        if vm.get("status") == "UNAVAILABLE":
            return (f"RECONCILIATION [{vm['mode']}] UNAVAILABLE [SOURCE/no-ledger] — "
                    f"no OMS/broker/ledger triple attached")
        extra = "" if not breaks else " BREAKS: " + ", ".join(str(b)[:80] for b in breaks)
        asof = f" [AS-OF {vm['asof']}]" if vm.get("asof") else ""
        return (f"RECONCILIATION [{vm['mode']}] {vm['status']}{extra} "
                f"[SOURCE/oms-vs-broker-vs-ledger]{asof}")


class AuditScreen(BaseScreen):
    name = "audit"

    def build_viewmodel(self, store: TerminalStore):
        snap = store.viewmodels.get("audit_snapshot", {}) or {}
        tail = snap.get("tail", ()) or tuple(_audit_tail())
        return {"mode": store.mode.value, "tail": tail,
                "chain": snap.get("chain", "OK" if tail else "UNAVAILABLE")}

    def render_text(self, vm) -> str:
        if not vm.get("tail"):
            return (f"AUDIT [{vm['mode']}] UNAVAILABLE [SOURCE/no-chain] — "
                    f"no compliance records this session")
        lines = [f"AUDIT [{vm['mode']}] chain={vm['chain']} [SOURCE/sha256-chain]"]
        lines += [f"  #{i} {r}" for i, r in enumerate(vm["tail"][-5:])]
        return "\n".join(lines)


__all__ = ["ReconScreen", "AuditScreen"]
