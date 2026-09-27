"""L7: supervisor (schema-validated tools + critic + risk gate). L8: ledger/recon/audit. Red-button."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib, json
from datetime import datetime, timezone
from decimal import Decimal

# ---------- L7 ----------
TOOLS = ("query_pit_universe", "compute_orthogonal_ic", "solve_hrp_portfolio", "run_var_stress_test")

@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str; args: dict
    def validate(self) -> None:
        if self.name not in TOOLS:
            raise ValueError(f"unknown tool {self.name} (hallucination-blocked)")
        if not isinstance(self.args, dict):
            raise ValueError("tool args must be object")
        req = {"query_pit_universe": ("asof",), "compute_orthogonal_ic": ("alpha",),
               "solve_hrp_portfolio": ("cov",), "run_var_stress_test": ("returns",)}[self.name]
        for k in req:
            if k not in self.args:
                raise ValueError(f"tool {self.name} missing arg {k}")

@dataclass(frozen=True, slots=True)
class Evidence:
    hypothesis: str; tool: ToolCall; result_hash: str; critic_pass: bool

class AdversarialCritic:
    def review(self, hypothesis: str, result: object) -> bool:
        if not hypothesis or not isinstance(hypothesis, str):
            return False
        if result is None:
            return False
        banned = ("guaranteed", "risk-free", "can't lose", "100%")
        return not any(b in hypothesis.lower() for b in banned)

class Supervisor:
    """ReAct supervisor: hypothesis -> validated tool -> critic -> risk gate. Never emits orders directly."""
    def __init__(self) -> None:
        self.critic = AdversarialCritic()
        self.memory: list[Evidence] = []
    def step(self, hypothesis: str, call: ToolCall, result: object, risk_pass: bool) -> Evidence:
        call.validate()
        ok = self.critic.review(hypothesis, result) and bool(risk_pass)
        h = hashlib.sha256(json.dumps(result, sort_keys=True, default=str).encode()).hexdigest()[:16]
        ev = Evidence(hypothesis, call, h, ok)
        self.memory.append(ev)
        if not ok:
            raise ValueError("supervisor gate blocked: critic or risk gate failed (fail-closed)")
        return ev

# ---------- L8 ----------
@dataclass
class Fill:
    order_id: str; symbol: str; qty: Decimal; price: Decimal

class Ledger:
    """3-way reconciliation: OMS expected vs broker fills vs custodian settled. SHA-256 audit chain."""
    def __init__(self) -> None:
        self.oms: dict[str, Decimal] = {}
        self.broker: dict[str, Decimal] = {}
        self.custodian: dict[str, Decimal] = {}
        self.chain: list[str] = []
        self._prev = "GENESIS"
    def _audit(self, event: str) -> None:
        h = hashlib.sha256(f"{self._prev}|{datetime.now(timezone.utc).isoformat()}|{event}".encode()).hexdigest()
        self.chain.append(h); self._prev = h
    def book_oms(self, symbol: str, qty: Decimal) -> None:
        self.oms[symbol] = self.oms.get(symbol, Decimal("0")) + qty
        self._audit(f"OMS {symbol} {qty}")
    def book_broker(self, f: Fill) -> None:
        self.broker[f.symbol] = self.broker.get(f.symbol, Decimal("0")) + f.qty
        self._audit(f"BROKER {f.order_id} {f.symbol} {f.qty}@{f.price}")
    def book_custodian(self, symbol: str, qty: Decimal) -> None:
        self.custodian[symbol] = self.custodian.get(symbol, Decimal("0")) + qty
        self._audit(f"CUSTODIAN {symbol} {qty}")
    def reconcile(self) -> dict[str, tuple[Decimal, Decimal, Decimal]]:
        syms = set(self.oms) | set(self.broker) | set(self.custodian)
        gaps = {s: (self.oms.get(s, Decimal("0")), self.broker.get(s, Decimal("0")), self.custodian.get(s, Decimal("0")))
                for s in syms if not (self.oms.get(s, Decimal("0")) == self.broker.get(s, Decimal("0")) == self.custodian.get(s, Decimal("0")))}
        if gaps:
            raise ValueError(f"reconciliation gap: {gaps}")
        return {}

# ---------- Structured tool-calling registry (Step 3 target) ----------
# The supervisor never writes trades; it only calls registered tools.
# Each entry maps a validated tool name -> "module:qualified_symbol" for the
# deterministic runtime to import and execute. Kept as data (not live imports)
# so delta_omega stays dependency-free and import-cycle safe.
TOOL_REGISTRY: dict[str, str] = {
    # Canonical L7 tool names (validated by ToolCall.validate).
    "query_pit_universe": "delta_omega.pit:PITStore.point_in_time",
    "compute_orthogonal_ic": "delta_omega.alpha_risk:orthogonalize",
    "solve_hrp_portfolio": "delta_omega.portfolio_exec:hrp_weights",
    "run_var_stress_test": "delta_omega.alpha_risk:evt_var_es",
    # Step-1 bridge aliases used by docs / live engine call-sites.
    "query_market_state": "delta_omega.pit:PITStore.point_in_time",
    "calculate_factor_risk": "delta_omega.alpha_risk:factor_portfolio_var",
    "run_hrp_allocation": "delta_omega.portfolio_exec:hrp_weights",
    "check_red_button": "delta_omega.agent_ledger_gate:red_button",
}


class RiskHaltException(RuntimeError):
    """Uncatchable-by-policy halt raised when the red-button gate trips.

    Callers must let this propagate: it signals crossed NBBO, clock
    inversion, reconciliation breaks, or other fail-closed conditions.
    (Catch only at the top-level supervisor to freeze trading.)
    """


# ---------- Red-button ----------
@dataclass(frozen=True, slots=True)
class GateState:
    bid: float; ask: float; day_loss: float; day_limit: float
    pbo: float; dsr: float; demo_path_used: bool; pos_adv_ratio: float
    beta_drift: float; beta_tol: float; clock_ok: bool; recon_ok: bool; collar_ok: bool

def red_button(s: GateState) -> list[str]:
    trips: list[str] = []
    if not s.clock_ok: trips.append("1:clock-inversion")
    if not (s.ask > s.bid > 0): trips.append("2:zero-bid/crossed")
    if s.pbo > 0.15: trips.append("3:pbo")
    if s.day_loss > s.day_limit: trips.append("4:drawdown")
    if not s.recon_ok: trips.append("5:recon-gap")
    if s.dsr < 0.99: trips.append("6:dsr")
    if not s.collar_ok: trips.append("7:collar")
    if s.demo_path_used: trips.append("8:demo-path")
    if s.pos_adv_ratio > 0.10: trips.append("9:liquidity-horizon")
    if abs(s.beta_drift) > s.beta_tol: trips.append("10:factor-neutrality")
    return trips
