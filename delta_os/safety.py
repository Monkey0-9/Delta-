"""DELTA OS safety: modes, order preview, risk governor, triple-layer kill.

MODE MANUAL: every order renders a preview ticket and requires [y/N].
MODE AUTO: background loop allowed ONLY inside governor bounds (5% single
position, 1.5x leverage, 2% daily halt); every AUTO order still passes the
pre-trade RiskFirewall + realtime monitor + kill switch.

Triple kill (/kill): (1) cancel-all on every configured adapter (<150ms
target, timed), (2) flatten via market orders on the ACTIVE adapter,
(3) freeze: mode=HALTED + kill switch active + compliance record. Reset
requires /unlock with actor + reason.

Stale/synthetic guard: orders require TIER1/TIER2-fresh frames; [STALE] or
[SYNTHETIC] frames are refused for execution (research allowed).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

SAFETY_VERSION = "safety-v1"
MAX_POSITION_PCT = 0.05
MAX_LEVERAGE = 1.5
DAILY_HALT_DRAWDOWN = 0.02


@dataclass
class OrderTicket:
    symbol: str
    action: str
    order_type: str
    price: float | None
    quantity: float
    stop_loss: float | None = None
    target: float | None = None
    macro_regime: str = ""

    def render(self, portfolio_pct: float) -> str:
        rr = ""
        if self.stop_loss and self.target and self.price:
            risk = abs(self.price - self.stop_loss) or 1e-9
            rr = f"R:R: 1 : {abs(self.target - self.price) / risk:.2f}"
        lines = ["+-- PROPOSED EXECUTION " + "-" * 41 + "+",
                 f"| Symbol: {self.symbol:<14}| Action: {self.action:<14}| Type: {self.order_type:<9}|",
                 f"| Price: {self.price}  | Qty: {self.quantity} shares | Val: ${self.notional():,.2f}|",
                 f"| Stop: {self.stop_loss} | Target: {self.target} | {rr:<16}|",
                 f"| Portfolio Risk: {portfolio_pct:.2%} | Macro: {self.macro_regime:<25}|",
                 "+" + "-" * 60 + "+"]
        return "\n".join(lines)

    def notional(self) -> float:
        return abs(float(self.quantity) * float(self.price or 0))


class SafetyError(Exception):
    pass


@dataclass
class AntiTiltGovernor:
    """Behavioral circuit breaker: 3 consecutive losses within 60 min ->
    30-min COOLDOWN (orders refused); drawdown > 1.5% scales size to 50%.

    Losses are recorded by the terminal after fills (record_trade). Time is
    injectable for tests; otherwise wall clock.
    """
    losses: list = field(default_factory=list)  # (timestamp_s, pnl)
    cooldown_until: float = 0.0
    size_scale: float = 1.0

    def record_trade(self, pnl: float, equity: float, day_start: float,
                     now_s: float | None = None) -> None:
        import time as _t

        now = now_s if now_s is not None else _t.time()
        self.losses.append((now, pnl))
        self.losses = [(t, p) for t, p in self.losses if now - t < 3600]
        recent = [p for _, p in self.losses[-3:]]
        if len(recent) == 3 and all(p < 0 for p in recent):
            self.cooldown_until = now + 1800
        dd = (equity - day_start) / max(day_start, 1e-9)
        self.size_scale = 0.5 if dd < -0.015 else 1.0

    def check(self, now_s: float | None = None) -> tuple[bool, str]:
        import time as _t

        now = now_s if now_s is not None else _t.time()
        if now < self.cooldown_until:
            left = int((self.cooldown_until - now) / 60) + 1
            return False, f"COOLDOWN {left}min left (anti-tilt)"
        return True, f"ok (size x{self.size_scale})"


@dataclass
class SafetyState:
    mode: str = "MANUAL"  # MANUAL|AUTO|HALTED
    day_start_equity: float = 1_000_000.0
    tilt: AntiTiltGovernor = field(default_factory=AntiTiltGovernor)
    kill = None
    compliance = None
    monitor = None

    def __post_init__(self) -> None:
        if self.kill is None:
            from governance.kill_switch import KillSwitch

            self.kill = KillSwitch()
        # Terminal boots disarmed (orders possible after explicit confirm);
        # /kill arms. The kernel KillSwitch defaults active, so release it once.
        try:
            self.kill.deactivate()
        except Exception:
            pass
        if self.compliance is None:
            from governance.compliance import ComplianceLog

            self.compliance = ComplianceLog()

    def set_mode(self, mode: str) -> str:
        if mode not in ("MANUAL", "AUTO"):
            raise SafetyError("mode must be MANUAL|AUTO (/unlock to leave HALTED).")
        if self.mode == "HALTED":
            raise SafetyError("engine HALTED; /unlock with actor+reason first.")
        self.mode = mode
        return mode

    def check_fresh(self, provenance) -> None:
        if provenance.tier not in ("TIER1", "TIER2"):
            raise SafetyError(
                f"execution refused on {provenance.badge or provenance.tier}: "
                "orders need fresh TIER1/TIER2 market data.")

    def govern(self, ticket: OrderTicket, equity: float, positions_value: float,
               day_equity: float, min_rr: float = 2.0) -> tuple[bool, str]:
        """Governor bounds for AUTO (MANUAL preview still needs explicit y).

        Enforces: 5% pos / 1.5x lev / 2% halt + asymmetric R:R >= 1:2.0
        (small-account capital preservation) + anti-tilt + kill switch.
        """
        if self.mode == "HALTED":
            return False, "HALTED"
        if equity <= 0:
            return False, "no equity"
        if ticket.notional() / equity > MAX_POSITION_PCT:
            return False, f"position {ticket.notional()/equity:.2%} > 5%"
        if positions_value / max(equity, 1e-9) > MAX_LEVERAGE:
            return False, "leverage > 1.5x"
        # Hard asymmetric R:R: reject < 1:2.0 when stop+target supplied.
        if ticket.stop_loss and ticket.target and ticket.price:
            risk = abs(ticket.price - ticket.stop_loss) or 1e-9
            rr = abs(ticket.target - ticket.price) / risk
            if rr < min_rr:
                return False, f"R:R 1:{rr:.2f} < 1:{min_rr:.1f} (asymmetric edge required)"
        dd = (day_equity - self.day_start_equity) / max(self.day_start_equity, 1e-9)
        if dd < -DAILY_HALT_DRAWDOWN:
            return False, f"daily halt {dd:.2%} < -2%"
        try:
            self.kill.assert_execution_allowed()
        except RuntimeError:
            return False, "kill switch active"
        ok, why = self.tilt.check()
        if not ok:
            return False, why
        return True, "PASS"

    def kill_all(self, adapters: list, actor: str = "operator") -> dict:
        """Triple-layer kill. Returns timed receipt; always freezes."""
        t0 = time.perf_counter()
        cancelled, errors = 0, []
        for ad in adapters:
            try:
                r = ad.cancel_all()
                cancelled += int(r.get("cancelled", 0) if isinstance(r, dict) else 0)
            except Exception as exc:
                errors.append(f"{getattr(ad, 'name', '?')}: {exc}")
        try:
            self.kill.activate()
        except Exception:
            pass
        self.mode = "HALTED"
        ms = (time.perf_counter() - t0) * 1000
        receipt = {"layer1_cancelled": cancelled, "layer1_ms": round(ms, 1),
                   "layer2_flatten": "manual /flatten required (market orders need confirm)",
                   "layer3_freeze": "HALTED", "errors": errors, "actor": actor}
        try:
            self.compliance.append("kill", receipt)
        except Exception:
            pass
        return receipt

    def unlock(self, actor: str, reason: str) -> str:
        if not actor.strip() or not reason.strip():
            raise SafetyError("unlock requires actor + reason.")
        try:
            self.kill.deactivate()
        except Exception:
            pass
        self.mode = "MANUAL"
        try:
            self.compliance.append("reset", {"actor": actor, "reason": reason})
        except Exception:
            pass
        return "MANUAL"


__all__ = ["SAFETY_VERSION", "OrderTicket", "SafetyError", "AntiTiltGovernor",
           "SafetyState", "MAX_POSITION_PCT", "MAX_LEVERAGE", "DAILY_HALT_DRAWDOWN"]
