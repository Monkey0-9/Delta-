from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Numeric pre-trade limits. Versioned; most-restrictive wins.

    Units (P0 fix): qty fields are SHARES, notional fields are CURRENCY.
    Never compare across units.
    """

    version: str = "limits-v1"
    max_order_qty: Decimal = Decimal("1000")  # shares
    max_order_notional: Decimal = Decimal("1000000")  # currency
    max_intraday_position: Decimal = Decimal("5000")  # shares (qty)
    max_position_notional: Decimal = Decimal("5000000")  # currency
    max_gross_exposure: Decimal = Decimal("5000000")
    max_leverage: Decimal = Decimal("3")
    price_tolerance_bps: Decimal = Decimal("100")  # 1% from ref
    max_duplicative_orders: int = 5
    duplicative_window_s: int = 10
    max_messages_per_s: int = 100
    stale_data_ttl_s: int = 5
    max_var_notional: Decimal | None = None  # optional VaR cap (absolute)
    var_alpha: Decimal = Decimal("0.95")

    def __post_init__(self) -> None:
        if self.max_order_qty <= 0 or self.max_order_notional <= 0:
            raise ValueError("order limits must be positive.")

    @classmethod
    def from_mandate(cls, mandate: object) -> RiskLimits:
        """Bind a TradingMandate to hard risk ceilings (most-restrictive wins).

        Never widens limits: mandate can only tighten vs defaults.
        Unit-safe (P0): notional caps map to notional fields, qty untouched.
        """
        base = cls()
        try:
            order_cap = mandate.max_order_notional_effective  # type: ignore[attr-defined]
        except Exception:
            order_cap = getattr(mandate, "max_order_notional", base.max_order_notional)
        try:
            pos_cap = mandate.max_position_notional_effective  # type: ignore[attr-defined]
        except Exception:
            pos_cap = getattr(mandate, "max_position_notional", base.max_position_notional)
        order_notional = min(Decimal(str(order_cap)), base.max_order_notional)
        pos_notional = min(Decimal(str(pos_cap)), base.max_position_notional)
        return cls(
            version=base.version,
            max_order_qty=base.max_order_qty,
            max_order_notional=order_notional,
            max_intraday_position=base.max_intraday_position,
            max_position_notional=pos_notional,
            max_gross_exposure=min(pos_notional, base.max_gross_exposure),
            max_leverage=base.max_leverage,
            price_tolerance_bps=base.price_tolerance_bps,
            max_duplicative_orders=base.max_duplicative_orders,
            duplicative_window_s=base.duplicative_window_s,
            max_messages_per_s=base.max_messages_per_s,
            stale_data_ttl_s=base.stale_data_ttl_s,
            max_var_notional=base.max_var_notional,
            var_alpha=base.var_alpha,
        )

    @classmethod
    def from_mapping(cls, data: dict) -> RiskLimits:
        """Load from config/paper.yaml-style mapping. Unknown keys ignored."""
        risk = data.get("risk", data)
        kwargs: dict = {}
        for f in (
            "version", "max_order_qty", "max_order_notional",
            "max_intraday_position", "max_position_notional",
            "max_gross_exposure", "max_leverage",
            "price_tolerance_bps", "max_duplicative_orders",
            "duplicative_window_s", "max_messages_per_s", "stale_data_ttl_s",
            "max_var_notional", "var_alpha",
        ):
            if f in risk:
                v = risk[f]
                if f in {"version"}:
                    kwargs[f] = str(v)
                elif f in {"max_duplicative_orders", "duplicative_window_s", "max_messages_per_s", "stale_data_ttl_s"}:
                    kwargs[f] = int(v)
                else:
                    kwargs[f] = Decimal(str(v))
        return cls(**kwargs)

    @classmethod
    def from_paper_yaml(cls, path: str = "config/paper.yaml") -> RiskLimits:
        try:
            import yaml  # type: ignore
        except Exception:
            yaml = None  # type: ignore
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        if yaml is not None:
            return cls.from_mapping(dict(yaml.safe_load(text) or {}))
        # Minimal fallback parser for flat `key: value` under risk:.
        data: dict = {}
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or ":" not in s:
                continue
            k, _, v = s.partition(":")
            data[k.strip()] = v.strip()
        return cls.from_mapping({"risk": data})
