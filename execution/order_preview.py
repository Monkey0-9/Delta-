"""Phases 29-30 — Order preview pipeline. NL never becomes a live order.

buy 100 NVDA -> resolve(security, account, broker, mode, price, type, quote,
risk, permissions) -> ORDER PREVIEW -> [SUBMIT][CANCEL]. Multi-broker plans
show per-venue allocation with aggregate risk BEFORE submission.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderPreview:
    instrument_id: str
    symbol: str
    side: str
    qty: float
    order_type: str
    price: float | None
    account: str
    broker: str
    environment: str
    mode: str
    notional: float | None
    risk: str = "PENDING"
    provenance: str = ""
    confirmed: bool = False

    def render(self) -> str:
        px = f"{self.price:,.2f}" if self.price is not None else "UNAVAILABLE"
        nt = f"{self.notional:,.2f}" if self.notional is not None else "UNAVAILABLE"
        return (f"ORDER PREVIEW\n{self.symbol} {self.side} {self.qty:g}\n"
                f"Account {self.account}\nBroker {self.broker}\nMode {self.mode}\n"
                f"Env {self.environment}\nReference {px}\nRisk {self.risk}\n"
                f"Estimated Notional {nt}\n[SUBMIT] [CANCEL]")


def preview_order(*, instrument_id: str, symbol: str, side: str, qty: float,
                  order_type: str, price: float | None, account: str,
                  broker: str, environment: str, mode: str,
                  risk: str, provenance: str) -> OrderPreview:
    if environment == "LIVE" and mode in ("RESEARCH", "SIM"):
        raise ValueError("LIVE order in RESEARCH/SIM mode — blocked")
    notional = price * qty if price is not None else None
    return OrderPreview(instrument_id, symbol, side.upper(), qty, order_type,
                        price, account, broker, environment, mode,
                        notional, risk, provenance)


def multi_account_plan(total_qty: float, legs: list[dict]) -> list[dict]:
    """Explicit allocation policy output; aggregate risk runs before submit."""
    if abs(sum(l["qty"] for l in legs) - total_qty) > 1e-9:
        raise ValueError("legs do not sum to total — blocked")
    return legs


__all__ = ["OrderPreview", "preview_order", "multi_account_plan"]
