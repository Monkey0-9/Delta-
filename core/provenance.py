"""Phases 32/92-95 — Provenance for every number + research/model/execution chains.

Money/price without provenance is refused at render. Research runs carry
dataset/model hashes; orders chain REQ->PLAN->RISK->ORDER->ACK->FILL->REC.
"""
from __future__ import annotations

from dataclasses import dataclass, field


QUALITIES = ("LIVE", "REALTIME", "DELAYED", "HISTORICAL", "PAPER", "SIM",
             "SYNTHETIC", "STALE", "DEGRADED", "UNAVAILABLE")


@dataclass(frozen=True)
class Provenance:
    source: str = ""
    quality: str = "UNAVAILABLE"
    asof: str = ""
    venue: str = ""
    provider: str = ""

    def label(self) -> str:
        if self.quality in ("UNAVAILABLE", ""):
            return "UNAVAILABLE"
        base = f"{self.quality}"
        if self.provider:
            base += f" provider:{self.provider}"
        if self.asof:
            base += f" as-of:{self.asof}"
        if self.venue:
            base += f" venue:{self.venue}"
        return base


def render_money(amount: float | None, prov: Provenance) -> str:
    if amount is None or prov.quality == "UNAVAILABLE":
        return "UNAVAILABLE"
    if prov.quality in ("SYNTHETIC", "SIM"):
        return f"{amount:,.2f} [{prov.label()}]"
    return f"{amount:,.2f} [{prov.label()}]"


@dataclass
class ResearchRecord:
    hypothesis: str = ""
    dataset_id: str = ""
    dataset_hash: str = ""
    model: str = ""
    model_version: str = ""
    effort: str = "MEDIUM"
    params_hash: str = ""
    result_hash: str = ""


@dataclass
class ExecutionChain:
    request_id: str = ""
    plan_id: str = ""
    risk_id: str = ""
    order_id: str = ""
    fill_ids: list = field(default_factory=list)
    reconcile_id: str = ""

    def lineage(self) -> str:
        return (f"{self.request_id} -> {self.plan_id} -> {self.risk_id} -> "
                f"{self.order_id} -> {self.fill_ids} -> {self.reconcile_id}")


__all__ = ["QUALITIES", "Provenance", "render_money",
           "ResearchRecord", "ExecutionChain"]
