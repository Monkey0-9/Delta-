"""Universal Broker Adapter: paper / Alpaca / IBKR behind one interface.

- PaperAdapter: wraps research.real_loop.paper_broker.PaperLedger (deterministic
  seed) with cancel-all + positions/cash. Always available.
- AlpacaAdapter: Trade API v2 over httpx. Default base = paper URL. test()
  calls GET /v2/account (auth check, returns buying power). Orders via POST
  /v2/orders. Live base URL REFUSED unless live_armed=True AND explicit
  approver (defense in depth with brokers.live).
- IBKRAdapter: Client Portal Web API. Requires host:port of a running IBEAM/
  gateway; status() reports UNCONFIGURED until set, then sessions over httpx.
  Honest stub: no fake fills, ever.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

UBA_VERSION = "uba-v1"
ALPACA_PAPER = "https://paper-api.alpaca.markets"
ALPACA_LIVE = "https://api.alpaca.markets"


class BrokerError(Exception):
    pass


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

    def cancel_all(self) -> dict:
        n = 0
        for o in self._ledger.orders.values():
            if o.status in ("NEW", "PARTIAL"):
                o.status = "CANCELLED"
                n += 1
        return {"cancelled": n}

    def positions(self, prices: dict) -> dict:
        return self._ledger.reconcile(prices)


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


@dataclass
class IBKRAdapter:
    host: str = ""  # e.g. "https://localhost:5000"
    name: str = "ibkr"
    timeout_s: float = 10.0

    def status(self) -> dict:
        if not self.host:
            return {"broker": "ibkr", "connected": False,
                    "error": "no gateway host configured (/broker connect ibkr)."}
        import httpx

        try:
            r = httpx.get(f"{self.host.rstrip('/')}/v1/api/iserver/auth/status",
                          timeout=self.timeout_s, verify=False)
            if r.status_code != 200:
                return {"broker": "ibkr", "connected": False,
                        "error": f"HTTP {r.status_code}"}
            return {"broker": "ibkr", "connected": bool(r.json().get("authenticated")),
                    "detail": r.json()}
        except Exception as exc:
            return {"broker": "ibkr", "connected": False, "error": str(exc)[:200]}

    def submit(self, *a, **k) -> dict:
        raise BrokerError("IBKR order routing not enabled in this build; "
                          "paper/Alpaca paths only.")

    def cancel_all(self) -> dict:
        raise BrokerError("IBKR cancel-all not enabled in this build.")


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


__all__ = ["UBA_VERSION", "BrokerError", "PaperAdapter", "AlpacaAdapter",
           "IBKRAdapter", "BrokerRouter"]
