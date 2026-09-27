from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CostModel:
    """Explicit transaction-cost model. Defaults are non-zero by policy."""

    commission_rate: Decimal = Decimal("0.0005")
    spread_bps: Decimal = Decimal("2")
    slippage_bps: Decimal = Decimal("5")
    impact_coef: Decimal = Decimal("0.1")  # sqrt-impact scale
    fee_per_share: Decimal = Decimal("0.0")

    def total_cost(self, *, price: Decimal, quantity: Decimal, adv: Decimal | None = None) -> Decimal:
        notional = price * quantity
        commission = notional * self.commission_rate
        spread = notional * self.spread_bps / Decimal("10000")
        slippage = notional * self.slippage_bps / Decimal("10000")
        impact = Decimal("0")
        if adv is not None and adv > 0:
            participation = quantity / adv
            impact = notional * self.impact_coef * participation.sqrt() if hasattr(participation, "sqrt") else notional * self.impact_coef * Decimal(str(float(participation) ** 0.5))
        fees = self.fee_per_share * quantity
        return commission + spread + slippage + impact + fees
