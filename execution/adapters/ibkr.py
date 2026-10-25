"""Interactive Brokers (IBKR) Client Portal / Gateway Native Adapter.

Implements institutional IBKR REST API lifecycle:
- Gateway auth status check & SSO keepalive
- Contract search & ConId symbol resolution
- Account summary & positions fetch
- Order submission, modification, and cancellation
- Cancel-all working orders
- Local vs IBKR 3-way position reconciliation

Kill-board policy (fail-closed): every mutating call (submit / cancel /
cancel_all) REQUIRES a bound ``kill_board``. ``kill_board=None`` refuses
with IBKRError — an unbound adapter must never admit a live order on the
strength of the ARMED flag alone. There is deliberately NO persisted-marker
fallback here (unlike the paper broker): live orders need an explicit,
in-process board, never an ambient file. Read-only calls (status /
keepalive / resolve_contract / positions) need no board.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger("DELTA.Execution.IBKR")


class IBKRError(Exception):
    pass


def _kill_reports_halt(obj: Any) -> tuple[bool, str]:
    """Duck-type kill probe: board, lone switch, or flag object. Fail-closed
    on unrecognized shapes (unknown state blocks, never admits)."""
    if obj is None:
        return False, ""
    check = getattr(obj, "check", None)
    if callable(check):
        try:
            check()
        except Exception as exc:
            return True, f"kill switch active: {exc}"
        return False, ""
    any_active = getattr(obj, "any_active", None)
    if callable(any_active):
        try:
            if any_active():
                return True, "kill switch active: board reports halt"
            return False, ""
        except Exception as exc:
            return True, f"kill probe failed fail-closed: {exc}"
    active = getattr(obj, "active", None)
    if isinstance(active, bool):
        return (True, "kill switch active") if active else (False, "")
    return True, "unrecognized kill state: fail-closed halt"


@dataclass
class IBKRClientPortalAdapter:
    """Live IBKR gateway adapter. Mutating calls require ``kill_board``.

    ``kill_board`` must be a board/switch/flag object understood by
    ``_kill_reports_halt`` (``check()`` / ``any_active()`` / ``active``).
    Passing ``None`` refuses every mutating call fail-closed — see the
    module docstring for the policy. ``stale_ttl_s`` bounds quote age.
    """

    host: str = "https://localhost:5000"
    account_id: str = ""
    timeout_s: float = 10.0
    verify_ssl: bool = True
    kill_board: Any = None
    stale_ttl_s: float = 5.0
    _tls_warned: bool = field(default=False, repr=False, compare=False)

    def _tls_verify(self) -> bool:
        if not self.verify_ssl and not self._tls_warned:
            logger.warning(
                "IBKR verify_ssl=False: TLS verification disabled (explicit "
                "opt-out; MITM-able).")
            self._tls_warned = True
        return self.verify_ssl

    def _preflight(self, action: str, *, data_age_s: float | None = None) -> None:
        """Fail-closed gates for every mutating call. Raises IBKRError."""
        if self.kill_board is None:
            raise IBKRError(
                f"IBKR {action} refused: no kill board bound "
                "(live mutating calls require an explicit board)")
        halted, why = _kill_reports_halt(self.kill_board)
        if halted:
            raise IBKRError(f"IBKR {action} refused: {why}")
        if os.environ.get("DELTA_LIVE", "").upper() != "ARMED":
            raise IBKRError(
                f"IBKR {action} refused: DELTA_LIVE!=ARMED (live not armed)")
        if data_age_s is not None and data_age_s > self.stale_ttl_s:
            raise IBKRError(
                f"IBKR {action} refused: stale market data "
                f"(age {data_age_s:g}s > ttl {self.stale_ttl_s:g}s)")

    def _base_url(self) -> str:
        return self.host.rstrip("/")

    def status(self) -> Dict[str, Any]:
        """Query IBKR Client Portal authentication and gateway status."""
        import httpx

        url = f"{self._base_url()}/v1/api/iserver/auth/status"
        try:
            r = httpx.get(url, timeout=self.timeout_s, verify=self._tls_verify())
            if r.status_code != 200:
                return {
                    "broker": "ibkr",
                    "connected": False,
                    "error": f"Gateway HTTP {r.status_code}",
                }
            data = r.json()
            is_auth = bool(data.get("authenticated", False))
            return {
                "broker": "ibkr",
                "connected": is_auth,
                "authenticated": is_auth,
                "competing": data.get("competing", False),
                "connected_server": data.get("connected", False),
                "detail": data,
            }
        except Exception as exc:
            return {"broker": "ibkr", "connected": False, "error": str(exc)[:200]}

    def keepalive(self) -> bool:
        """Ping IBKR SSO session keepalive."""
        import httpx

        url = f"{self._base_url()}/v1/api/sso/validate"
        try:
            r = httpx.get(url, timeout=self.timeout_s, verify=self._tls_verify())
            return r.status_code == 200
        except Exception:
            return False

    def resolve_contract(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> int:
        """Search symbol to resolve IBKR ConId integer across 150+ international markets."""
        import httpx

        url = f"{self._base_url()}/v1/api/iserver/secdef/search"
        payload: Dict[str, Any] = {"symbol": symbol, "name": False, "secType": sec_type}
        if exchange:
            payload["exchange"] = exchange
        if currency:
            payload["currency"] = currency
        try:
            r = httpx.post(url, json=payload, timeout=self.timeout_s, verify=self._tls_verify())
            if r.status_code == 200:
                results = r.json()
                if results and isinstance(results, list):
                    con_id = int(results[0].get("conid", 0))
                    if con_id > 0:
                        return con_id
            raise IBKRError(f"Contract resolution failed for symbol {symbol}: {r.text[:200]}")
        except Exception as exc:
            raise IBKRError(f"Failed to resolve contract for {symbol}: {exc}") from exc

    def positions(self) -> List[Dict[str, Any]]:
        """Fetch current open account positions."""
        import httpx

        if not self.account_id:
            raise IBKRError("account_id not configured.")

        url = f"{self._base_url()}/v1/api/portfolio/{self.account_id}/positions/0"
        try:
            r = httpx.get(url, timeout=self.timeout_s, verify=self._tls_verify())
            if r.status_code == 200:
                return r.json()
            raise IBKRError(f"Fetch positions failed HTTP {r.status_code}: {r.text[:200]}")
        except Exception as exc:
            raise IBKRError(f"Error fetching IBKR positions: {exc}") from exc

    def submit(
        self,
        symbol: str,
        side: str,  # 'BUY' or 'SELL'
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "LMT",  # 'LMT', 'MKT', 'STP'
        idempotency_key: str = "",
        data_age_s: float | None = None,
    ) -> Dict[str, Any]:
        """Submit order to IBKR Gateway API."""
        import httpx

        self._preflight("submit", data_age_s=data_age_s)
        if not self.account_id:
            raise IBKRError("account_id not configured for order submission.")

        con_id = self.resolve_contract(symbol)
        order_body = {
            "conid": con_id,
            "orderType": "LMT" if price else "MKT",
            "side": side.upper(),
            "quantity": quantity,
            "tif": "DAY",
        }
        if price:
            order_body["price"] = price
        if idempotency_key:
            order_body["cSystemArgs"] = idempotency_key[:30]

        payload = {"orders": [order_body]}
        url = f"{self._base_url()}/v1/api/iserver/account/{self.account_id}/orders"
        try:
            r = httpx.post(url, json=payload, timeout=self.timeout_s, verify=self._tls_verify())
            if r.status_code not in (200, 201):
                raise IBKRError(f"IBKR order submission rejected HTTP {r.status_code}: {r.text[:200]}")
            resp_data = r.json()
            order_id = ""
            status = "SUBMITTED"
            if isinstance(resp_data, list) and len(resp_data) > 0:
                order_id = str(resp_data[0].get("order_id", ""))
                status = str(resp_data[0].get("order_status", "SUBMITTED"))

            return {
                "order_id": order_id,
                "status": status,
                "symbol": symbol,
                "quantity": quantity,
                "price": price,
                "broker": "ibkr",
            }
        except IBKRError:
            raise
        except Exception as exc:
            raise IBKRError(f"IBKR submit order failed: {exc}") from exc

    def cancel_order(self, order_id: str, data_age_s: float | None = None) -> Dict[str, Any]:
        """Cancel specific order by order_id."""
        import httpx

        self._preflight("cancel", data_age_s=data_age_s)
        if not self.account_id:
            raise IBKRError("account_id not configured.")

        url = f"{self._base_url()}/v1/api/iserver/account/{self.account_id}/order/{order_id}"
        try:
            r = httpx.delete(url, timeout=self.timeout_s, verify=self._tls_verify())
            if r.status_code not in (200, 202):
                raise IBKRError(f"IBKR cancel failed HTTP {r.status_code}: {r.text[:200]}")
            return {"order_id": order_id, "status": "CANCELLED", "detail": r.json()}
        except Exception as exc:
            raise IBKRError(f"IBKR cancel failed: {exc}") from exc

    def cancel_all(self, data_age_s: float | None = None) -> Dict[str, Any]:
        """Cancel all working open orders."""
        import httpx

        self._preflight("cancel_all", data_age_s=data_age_s)
        if not self.account_id:
            raise IBKRError("account_id not configured.")

        url = f"{self._base_url()}/v1/api/iserver/account/{self.account_id}/orders"
        try:
            r = httpx.get(url, timeout=self.timeout_s, verify=self._tls_verify())
            cancelled_count = 0
            failed: list[dict[str, str]] = []
            if r.status_code == 200:
                orders = r.json().get("orders", [])
                for o in orders:
                    oid = str(o.get("orderId", ""))
                    if oid:
                        try:
                            self.cancel_order(oid, data_age_s=data_age_s)
                            cancelled_count += 1
                        except Exception as exc:
                            failed.append({"order_id": oid, "reason": str(exc)[:200]})
            return {"broker": "ibkr", "cancelled": cancelled_count, "failed": failed}
        except Exception as exc:
            raise IBKRError(f"IBKR cancel_all failed: {exc}") from exc


__all__ = ["IBKRError", "IBKRClientPortalAdapter"]
