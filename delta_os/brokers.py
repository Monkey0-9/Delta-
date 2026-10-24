"""Universal Broker Adapter: paper / Alpaca / IBKR behind one interface.

- PaperAdapter: wraps research.real_loop.paper_broker.PaperLedger (deterministic
  seed) with cancel-all + positions/cash + canonical AccountSnapshot. Always available.
- AlpacaAdapter: Trade API v2 over httpx. Default base = paper URL. test()
  calls GET /v2/account (auth check, returns buying power). Orders via POST
  /v2/orders. Live base URL REFUSED unless live_armed=True AND explicit
  approver (defense in depth with brokers.live).
- IBKRAdapter: Client Portal Web API. Requires host:port of a running IBEAM/
  gateway; status() reports UNCONFIGURED until set, then sessions over httpx.
  Honest stub: no fake fills, ever.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

UBA_VERSION = "uba-v2"
ALPACA_PAPER = "https://paper-api.alpaca.markets"
ALPACA_LIVE = "https://api.alpaca.markets"


class BrokerError(Exception):
    pass


@dataclass
class AccountSnapshot:
    """Authoritative point-in-time account and portfolio snapshot across brokers."""
    broker: str
    connected: bool
    cash: float
    equity: Optional[float]
    positions: Dict[str, float]
    market_values: Dict[str, float]
    prices: Dict[str, float]
    degraded: bool
    degraded_reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PaperAdapter:
    seed: int = 7
    name: str = "paper"

    def __post_init__(self) -> None:
        from research.real_loop import paper_broker as PB

        self._ledger = PB.PaperLedger(seed=self.seed)

    def status(self) -> dict:
        return {"broker": "paper", "connected": True, "cash": self._ledger.cash,
                "positions": len(self._ledger.positions)}

    def submit(self, symbol: str, side: str, quantity: float, price: float,
               idempotency_key: str = "") -> dict:
        o = self._ledger.submit(symbol, side.upper(), quantity, price,
                                idempotency_key=idempotency_key)
        return {"order_id": o.order_id, "status": o.status, "filled": o.filled,
                "avg_price": o.avg_price}

    def cancel(self, order_id: str) -> dict:
        return self._ledger.cancel(order_id)

    def cancel_all(self) -> dict:
        n = 0
        for o in self._ledger.orders.values():
            if o.status in ("NEW", "PARTIAL"):
                o.status = "CANCELLED"
                n += 1
        return {"cancelled": n}

    def positions(self, prices: dict) -> dict:
        return self._ledger.reconcile(prices)

    def get_account_snapshot(
        self, price_provider: Optional[Callable[[str], Optional[float]]] = None
    ) -> AccountSnapshot:
        cash = float(self._ledger.cash)
        positions: Dict[str, float] = {}
        market_values: Dict[str, float] = {}
        prices: Dict[str, float] = {}
        degraded = False
        degraded_reason = None

        for sym, pos in self._ledger.positions.items():
            if isinstance(pos, (int, float)):
                qty = float(pos)
            else:
                qty = float(getattr(pos, "quantity", getattr(pos, "qty", getattr(pos, "shares", 0.0))))
            if abs(qty) < 1e-9:
                continue
            positions[sym] = qty

            px: Optional[float] = None
            if price_provider is not None:
                try:
                    px = price_provider(sym)
                except Exception:
                    px = None

            if px is None or not (isinstance(px, (int, float)) and math.isfinite(px) and px > 0):
                degraded = True
                degraded_reason = (
                    f"Missing or unverified quote for position {sym}; cannot compute equity without live price."
                )
                prices[sym] = 0.0
                market_values[sym] = 0.0
            else:
                prices[sym] = float(px)
                market_values[sym] = qty * float(px)

        if degraded:
            equity = None
        else:
            equity = cash + sum(market_values.values())

        return AccountSnapshot(
            broker="paper",
            connected=True,
            cash=cash,
            equity=equity,
            positions=positions,
            market_values=market_values,
            prices=prices,
            degraded=degraded,
            degraded_reason=degraded_reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class AlpacaAdapter:
    key_id: str
    secret: str
    base_url: str = ALPACA_PAPER
    name: str = "alpaca"
    timeout_s: float = 10.0

    def __post_init__(self) -> None:
        if self.base_url.rstrip("/") == ALPACA_LIVE:
            raise BrokerError("live Alpaca base refused here; use brokers.live "
                              "authorization path.")

    def _headers(self) -> dict:
        return {"APCA-API-KEY-ID": self.key_id, "APCA-API-SECRET-KEY": self.secret}

    def status(self) -> dict:
        import httpx

        try:
            r = httpx.get(f"{self.base_url}/v2/account", headers=self._headers(),
                          timeout=self.timeout_s)
            if r.status_code != 200:
                return {"broker": "alpaca", "connected": False,
                        "error": f"HTTP {r.status_code}"}
            a = r.json()
            return {"broker": "alpaca", "connected": True,
                    "buying_power": a.get("buying_power"),
                    "cash": a.get("cash"), "paper": "paper" in self.base_url}
        except Exception as exc:
            return {"broker": "alpaca", "connected": False, "error": str(exc)[:200]}

    def submit(self, symbol: str, side: str, quantity: float, price: float | None,
               idempotency_key: str = "") -> dict:
        import httpx

        body = {"symbol": symbol, "side": side.lower(), "type": "limit" if price else "market",
                "time_in_force": "day", "qty": str(quantity)}
        if price:
            body["limit_price"] = str(price)
        if idempotency_key:
            body["client_order_id"] = idempotency_key[:48]
        try:
            r = httpx.post(f"{self.base_url}/v2/orders", headers=self._headers(),
                           json=body, timeout=self.timeout_s)
            if r.status_code not in (200, 201):
                raise BrokerError(f"Alpaca reject HTTP {r.status_code}: {r.text[:200]}")
            o = r.json()
            return {"order_id": o.get("id"), "status": o.get("status"),
                    "filled": o.get("filled_qty"), "avg_price": o.get("filled_avg_price")}
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"Alpaca submit failed: {exc}") from exc

    def cancel(self, order_id: str) -> dict:
        import httpx

        try:
            r = httpx.delete(
                f"{self.base_url}/v2/orders/{order_id}",
                headers=self._headers(),
                timeout=self.timeout_s,
            )
            if r.status_code in (200, 204):
                return {"order_id": order_id, "status": "CANCELLED"}
            if r.status_code == 404:
                return {"order_id": order_id, "status": "NOT_FOUND", "error": r.text[:200]}
            raise BrokerError(f"Alpaca cancel failed HTTP {r.status_code}: {r.text[:200]}")
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"Alpaca cancel failed: {exc}") from exc

    def cancel_all(self) -> dict:
        import httpx

        try:
            r = httpx.delete(f"{self.base_url}/v2/orders", headers=self._headers(),
                             timeout=self.timeout_s)
            if r.status_code not in (200, 207):
                raise BrokerError(f"cancel-all HTTP {r.status_code}.")
            return {"cancelled": r.json()}
        except BrokerError:
            raise
        except Exception as exc:
            raise BrokerError(f"Alpaca cancel-all failed: {exc}") from exc

    def get_account_snapshot(
        self, price_provider: Optional[Callable[[str], Optional[float]]] = None
    ) -> AccountSnapshot:
        import httpx

        st = self.status()
        if not st.get("connected"):
            return AccountSnapshot(
                broker="alpaca",
                connected=False,
                cash=0.0,
                equity=None,
                positions={},
                market_values={},
                prices={},
                degraded=True,
                degraded_reason=f"Alpaca disconnected: {st.get('error', 'unknown error')}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        try:
            r = httpx.get(f"{self.base_url}/v2/positions", headers=self._headers(), timeout=self.timeout_s)
            pos_list = r.json() if r.status_code == 200 else []
            positions: Dict[str, float] = {}
            market_values: Dict[str, float] = {}
            prices: Dict[str, float] = {}
            degraded = False
            degraded_reason = None

            for p in pos_list:
                sym = p.get("symbol", "")
                qty = float(p.get("qty", 0.0))
                positions[sym] = qty
                px = None
                if price_provider:
                    px = price_provider(sym)
                if px is None:
                    try:
                        px = float(p.get("current_price"))
                    except (ValueError, TypeError):
                        px = None
                if px is None or not math.isfinite(px):
                    degraded = True
                    degraded_reason = f"Missing quote for {sym}"
                    prices[sym] = 0.0
                    market_values[sym] = 0.0
                else:
                    prices[sym] = px
                    market_values[sym] = qty * px

            cash = float(st.get("cash", 0.0) or 0.0)
            equity = cash + sum(market_values.values()) if not degraded else None
            return AccountSnapshot(
                broker="alpaca",
                connected=True,
                cash=cash,
                equity=equity,
                positions=positions,
                market_values=market_values,
                prices=prices,
                degraded=degraded,
                degraded_reason=degraded_reason,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            return AccountSnapshot(
                broker="alpaca",
                connected=False,
                cash=0.0,
                equity=None,
                positions={},
                market_values={},
                prices={},
                degraded=True,
                degraded_reason=f"Failed to query Alpaca account: {exc}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )


@dataclass
class IBKRAdapter:
    host: str = ""  # e.g. "https://localhost:5000"
    account_id: str = ""
    name: str = "ibkr"
    timeout_s: float = 10.0

    def _client(self):
        from execution.adapters.ibkr import IBKRClientPortalAdapter
        return IBKRClientPortalAdapter(
            host=self.host, account_id=self.account_id, timeout_s=self.timeout_s
        )

    def status(self) -> dict:
        if not self.host:
            return {"broker": "ibkr", "connected": False,
                    "error": "no gateway host configured (/broker connect ibkr)."}
        try:
            return self._client().status()
        except Exception as exc:
            return {"broker": "ibkr", "connected": False, "error": str(exc)[:200]}

    def submit(self, symbol: str, side: str, quantity: float, price: float | None = None,
               idempotency_key: str = "") -> dict:
        if not self.host:
            raise BrokerError("IBKR gateway host not configured.")
        try:
            return self._client().submit(
                symbol=symbol, side=side, quantity=quantity, price=price,
                idempotency_key=idempotency_key
            )
        except Exception as exc:
            raise BrokerError(f"IBKR order submission failed: {exc}") from exc

    def cancel(self, order_id: str) -> dict:
        if not self.host:
            raise BrokerError("IBKR gateway host not configured.")
        try:
            return self._client().cancel_order(order_id)
        except Exception as exc:
            raise BrokerError(f"IBKR cancel order failed: {exc}") from exc

    def cancel_all(self) -> dict:
        if not self.host:
            raise BrokerError("IBKR gateway host not configured.")
        try:
            return self._client().cancel_all()
        except Exception as exc:
            raise BrokerError(f"IBKR cancel_all failed: {exc}") from exc

    def get_account_snapshot(
        self, price_provider: Optional[Callable[[str], Optional[float]]] = None
    ) -> AccountSnapshot:
        st = self.status()
        if not st.get("connected"):
            return AccountSnapshot(
                broker="ibkr",
                connected=False,
                cash=0.0,
                equity=None,
                positions={},
                market_values={},
                prices={},
                degraded=True,
                degraded_reason=f"IBKR disconnected: {st.get('error', 'unknown error')}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        # IBKR status returns portfolio cash / equity if available
        cash = float(st.get("cash", 0.0) or 0.0)
        return AccountSnapshot(
            broker="ibkr",
            connected=True,
            cash=cash,
            equity=float(st.get("equity", cash) or cash),
            positions={},
            market_values={},
            prices={},
            degraded=False,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


@dataclass
class BrokerRouter:
    paper: PaperAdapter = field(default_factory=PaperAdapter)
    alpaca: AlpacaAdapter | None = None
    ibkr: IBKRAdapter | None = None
    active: str = "paper"

    def use(self, name: str):
        if name == "paper":
            self.active = "paper"
        elif name == "alpaca" and self.alpaca is not None:
            self.active = "alpaca"
        elif name == "ibkr" and self.ibkr is not None:
            self.active = "ibkr"
        else:
            raise BrokerError(f"broker {name} not configured (/broker connect).")
        return self.active

    def current(self):
        return {"paper": self.paper, "alpaca": self.alpaca,
                "ibkr": self.ibkr}[self.active]

    def get_account_snapshot(
        self, price_provider: Optional[Callable[[str], Optional[float]]] = None
    ) -> AccountSnapshot:
        cur = self.current()
        if hasattr(cur, "get_account_snapshot"):
            return cur.get_account_snapshot(price_provider=price_provider)
        raise NotImplementedError(f"Broker adapter {cur} does not support get_account_snapshot")


__all__ = [
    "UBA_VERSION",
    "BrokerError",
    "AccountSnapshot",
    "PaperAdapter",
    "AlpacaAdapter",
    "IBKRAdapter",
    "BrokerRouter",
]
