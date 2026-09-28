"""Real tool-using research agent (item 6, W211-W220).

Identity + tool registry + RBAC + data-access policy + backtest/feature/
experiment/validation tools + report generator + memory writeback.

Hard rules:
- Tools execute ONLY via ToolRegistry.execute with granted permissions.
- The agent NEVER holds SUBMIT_ORDER/CANCEL_ORDER/ENABLE_AUTONOMOUS.
- Every tool call is traced (name, args hash, success, error).
- Memory writeback records hypothesis, metrics, stage, parent linkage.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field

from agent.runtime.types import AgentPermission, ToolCall, ToolResult
from agent.tools.registry import ToolRegistry

AGENT_VERSION = "research-agent-v1"

# The agent may hold exactly these — trading permissions are never granted.
AGENT_PERMISSIONS = frozenset({
    AgentPermission.READ_MARKET_DATA,
    AgentPermission.RUN_ANALYSIS,
    AgentPermission.RUN_SIMULATION,
    AgentPermission.READ_RISK,
})

FORBIDDEN = frozenset({
    AgentPermission.SUBMIT_ORDER,
    AgentPermission.CANCEL_ORDER,
    AgentPermission.ENABLE_AUTONOMOUS,
    AgentPermission.PROPOSE_TRADE,
})


def _arghash(args: dict) -> str:
    raw = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:12]


@dataclass
class AgentReport:
    agent_id: str
    hypothesis: str
    symbols: tuple[str, ...]
    tool_trace: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    stage: str = "hypothesis"  # hypothesis | validated | failed
    conclusion: str = ""
    memory_exp_id: str = ""

    def to_dict(self) -> dict:
        return {"agent": self.agent_id, "version": AGENT_VERSION,
                "hypothesis": self.hypothesis, "symbols": list(self.symbols),
                "tool_trace": self.tool_trace, "metrics": self.metrics,
                "stage": self.stage, "conclusion": self.conclusion,
                "memory_exp_id": self.memory_exp_id}


def _tool_fetch_bars(symbols: list[str], days: int = 180) -> dict:
    from research.real_loop.market_data import fetch_bars
    bars = fetch_bars(list(symbols), int(days))
    return {s: {"source": b.source, "hash": b.data_hash, "rows": len(b.frame)}
            for s, b in bars.items()}


def _tool_features(symbol: str, days: int = 180) -> dict:
    from research.real_loop.market_data import fetch_bars
    from research.real_loop.features import compute_features, FEATURE_VERSION
    bars = fetch_bars([symbol], int(days))
    bs = bars[symbol]
    feat = compute_features(bs.frame, symbol, bs.data_hash)
    return {"symbol": symbol, "feature_version": FEATURE_VERSION,
            "columns": list(feat.columns), "rows": len(feat),
            "data_hash": bs.data_hash, "source": bs.source}


def _tool_backtest(symbol: str, days: int = 365, costs_bps: float = 8.0) -> dict:
    from research.real_loop.market_data import fetch_bars
    from research.real_loop.features import compute_features
    from research.real_loop.walkforward import walk_forward
    bars = fetch_bars([symbol], int(days))
    bs = bars[symbol]
    feat = compute_features(bs.frame, symbol, bs.data_hash)
    px = bs.frame["close"].astype(float)
    return walk_forward(px, feat, costs_bps=float(costs_bps))


def _tool_validate(symbol: str, days: int = 365) -> dict:
    import pandas as pd
    from research.real_loop.market_data import fetch_bars
    from research.real_loop.features import compute_features
    from research.real_loop import alpha_stats as A
    bars = fetch_bars([symbol], int(days))
    bs = bars[symbol]
    feat = compute_features(bs.frame, symbol, bs.data_hash)
    px = bs.frame["close"].astype(float)
    sig_cols = [c for c in feat.columns if c.startswith(("mom_", "mr_z_", "trend_"))]
    sig = feat[sig_cols].mean(axis=1).fillna(0) if sig_cols else pd.Series(0.0, index=feat.index)
    fwd = px.pct_change(5).shift(-5)
    scores = sig.shift(2).reindex(fwd.index)
    ics = A.ic_series(scores, fwd)
    return {"rank_ic": A.rank_ic(scores, fwd), "icir": A.icir(ics),
            "half_life": A.ic_decay_half_life(ics), "hac_t": A.newey_west_t(fwd.dropna())}


class ResearchAgent:
    """Tool-using autonomous research loop with hard permission boundaries."""

    def __init__(self, agent_id: str, granted: frozenset[AgentPermission] | None = None,
                 memory=None) -> None:
        granted = AGENT_PERMISSIONS if granted is None else frozenset(granted)
        illegal = granted & FORBIDDEN
        if illegal:
            raise ValueError(f"agent may never hold: {sorted(p.value for p in illegal)}.")
        self.agent_id = agent_id
        self.granted = granted
        self.memory = memory
        self.registry = ToolRegistry()
        self._register_tools()

    def _register_tools(self) -> None:
        R, A, S = AgentPermission.READ_MARKET_DATA, AgentPermission.RUN_ANALYSIS, AgentPermission.RUN_SIMULATION
        self.registry.register(name="market_bars", description="Fetch PIT bars (fail-closed).",
                               function=_tool_fetch_bars, permissions=frozenset({R}))
        self.registry.register(name="feature_search", description="Compute PIT features.",
                               function=_tool_features, permissions=frozenset({R, A}))
        self.registry.register(name="backtest", description="Purged walk-forward backtest.",
                               function=_tool_backtest, permissions=frozenset({R, S}))
        self.registry.register(name="statistical_validation",
                               description="IC/ICIR/HAC validation gates.",
                               function=_tool_validate, permissions=frozenset({R, A}))

    def call(self, name: str, task_id, **args) -> ToolResult:
        return self.registry.execute(ToolCall(name, dict(args), task_id), self.granted)

    def run(self, hypothesis: str, symbols: tuple[str, ...], days: int = 365,
            parent_experiment_id: str = "") -> AgentReport:
        """Hypothesis -> bars -> features -> backtest -> validation -> memory."""
        if not hypothesis.strip():
            raise ValueError("hypothesis required.")
        rep = AgentReport(self.agent_id, hypothesis, tuple(symbols))
        tid = uuid.uuid4()

        def step(name: str, **args):
            res = self.call(name, tid, **args)
            rep.tool_trace.append({"tool": name, "args_hash": _arghash(args),
                                   "success": res.success,
                                   "error": res.error if not res.success else ""})
            return res

        r = step("market_bars", symbols=list(symbols), days=days)
        if not r.success:
            rep.stage, rep.conclusion = "failed", f"data unavailable: {r.error}"
            return self._writeback(rep, parent_experiment_id)
        r = step("feature_search", symbol=symbols[0], days=days)
        if not r.success:
            rep.stage, rep.conclusion = "failed", f"feature failure: {r.error}"
            return self._writeback(rep, parent_experiment_id)
        r = step("backtest", symbol=symbols[0], days=days)
        if not r.success:
            rep.stage, rep.conclusion = "failed", f"backtest failure: {r.error}"
            return self._writeback(rep, parent_experiment_id)
        wf = r.output if isinstance(r.output, dict) else {}
        rep.metrics["walkforward"] = wf
        r = step("statistical_validation", symbol=symbols[0], days=days)
        if r.success and isinstance(r.output, dict):
            rep.metrics["validation"] = r.output
        gate = wf.get("gate", {}) if isinstance(wf, dict) else {}
        if gate.get("pass"):
            rep.stage = "validated"
            rep.conclusion = f"PASS: OOS net {wf.get('oos_total_net')} over {wf.get('n_folds')} folds."
        else:
            rep.stage = "failed"
            rep.conclusion = (f"REJECT: OOS net {wf.get('oos_total_net')} "
                              f"fails {gate.get('rule', 'gate')}.")
        return self._writeback(rep, parent_experiment_id)

    def _writeback(self, rep: AgentReport, parent_id: str) -> AgentReport:
        if self.memory is None:
            return rep
        exp_id = f"AG-{self.agent_id}-{_arghash({'h': rep.hypothesis, 's': list(rep.symbols)})}"
        try:
            self.memory.record(exp_id, rep.hypothesis, rep.symbols, {},
                               rep.metrics.get("feature_version", ""), AGENT_VERSION,
                               rep.metrics, rep.stage, rep.conclusion, parent_id)
            rep.memory_exp_id = exp_id
        except Exception as exc:
            rep.tool_trace.append({"tool": "memory_writeback", "success": False,
                                   "error": f"{type(exc).__name__}: {exc}"})
        return rep


__all__ = ["AGENT_VERSION", "AGENT_PERMISSIONS", "FORBIDDEN", "AgentReport", "ResearchAgent"]
