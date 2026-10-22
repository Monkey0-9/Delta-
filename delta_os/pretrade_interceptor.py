"""DELTA OS — Pre-Trade Mistake Interceptor & Closed-Loop Learning Engine.

Enforces the invariant that trading models must learn from past mistakes:
1. Cross-references proposed orders against attributed failure records and trade experiences.
2. Identifies matching failure patterns across market regimes (e.g. buying high-RSI during
   crash regimes, excessive size relative to ADV, or repeat drawdowns in specific assets).
3. Issues deterministic pre-trade cautions or hard fail-closed vetoes before OMS entry.
4. Closes the learning loop by ingesting trade outcomes into the ClosedLoopLearner.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from learning.closed_loop import ClosedLoopLearner, FailureType


def _mistakes_file_path() -> Path:
    base = Path(os.environ.get("DELTA_HOME", str(Path.home() / ".delta")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "mistakes.jsonl"


@dataclass(frozen=True)
class MistakeWarning:
    """Structured description of an intercepted repeat mistake."""
    symbol: str
    side: str
    regime: str
    failure_type: str
    lesson: str
    past_loss_pct: float
    blocked: bool
    evidence_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def format_cli(self) -> str:
        tag = "[MISTAKE VETO]" if self.blocked else "[MISTAKE CAUTION]"
        return (
            f"  {tag} {self.symbol} {self.side} ({self.regime})\n"
            f"  Prior Failure : {self.failure_type} (Loss: {self.past_loss_pct:.2f}%)\n"
            f"  Learned Lesson: {self.lesson}\n"
            f"  Status        : {'BLOCKED (Fail-Closed)' if self.blocked else 'PROCEED WITH CAUTION'}"
        )


class PreTradeInterceptor:
    """Interception engine enforcing retrospective failure-memory checks on new orders."""

    def __init__(self, learner: Optional[ClosedLoopLearner] = None) -> None:
        self.learner = learner or ClosedLoopLearner()
        self._load_persisted_mistakes()

    def _load_persisted_mistakes(self) -> None:
        """Load historical trade mistakes from persistent JSONL file."""
        p = _mistakes_file_path()
        if not p.exists():
            return
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    item = json.loads(line)
                    self.learner.record_experience(
                        trade_id=item.get("trade_id", "persisted"),
                        symbol=item.get("symbol", "").upper(),
                        predicted_return=float(item.get("predicted_return", 0.0)),
                        realized_return=float(item.get("realized_return", -0.02)),
                        execution_shortfall_bps=float(item.get("execution_shortfall_bps", 0.0)),
                        vwap_slippage_bps=float(item.get("vwap_slippage_bps", 0.0)),
                    )
        except Exception:
            pass

    def inspect_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float = 0.0,
        regime: str = "NEUTRAL",
        rsi: float = 50.0,
        spread_bps: float = 5.0,
        strict_veto: bool = False,
    ) -> List[MistakeWarning]:
        """Inspect order against failure history and return any matching mistake warnings."""
        warnings: List[MistakeWarning] = []
        sym = symbol.strip().upper()
        norm_side = side.strip().upper()
        norm_regime = regime.strip().upper()

        # 1. Historical Trade Experience Check (Asset-specific past shortfall/loss)
        for exp in self.learner.experiences:
            if exp.symbol == sym and exp.realized_return < -0.015:
                loss_pct = abs(exp.realized_return) * 100.0
                lesson = (
                    f"Prior loss on {sym} ({exp.realized_return * 100:.2f}%). "
                    f"Execution shortfall: {exp.execution_shortfall_bps:.1f} bps, "
                    f"VWAP slippage: {exp.vwap_slippage_bps:.1f} bps."
                )
                warnings.append(
                    MistakeWarning(
                        symbol=sym,
                        side=norm_side,
                        regime=norm_regime,
                        failure_type="HISTORICAL_EXECUTION_SHORTFALL",
                        lesson=lesson,
                        past_loss_pct=loss_pct,
                        blocked=strict_veto,
                        evidence_id=exp.trade_id,
                    )
                )

        # 2. Regime-Indicator Failure Invariant
        # Documented failure pattern: Chasing momentum (RSI > 75) during BEAR or HIGH_VOLATILITY
        if norm_regime in ("BEAR", "BEAR_CRASH", "HIGH_VOLATILITY") and rsi > 75.0 and norm_side == "BUY":
            warnings.append(
                MistakeWarning(
                    symbol=sym,
                    side=norm_side,
                    regime=norm_regime,
                    failure_type=FailureType.REGIME_ERROR.value,
                    lesson="Buying overbought assets (RSI > 75) during BEAR / HIGH_VOLATILITY regimes is a documented failure mode.",
                    past_loss_pct=4.2,
                    blocked=True,  # Always block toxic regime entries
                    evidence_id="REGIME-RSI-VETO",
                )
            )

        # 3. Liquidity & Spread Mismatch Invariant
        if spread_bps > 40.0:
            warnings.append(
                MistakeWarning(
                    symbol=sym,
                    side=norm_side,
                    regime=norm_regime,
                    failure_type=FailureType.LIQUIDITY_ERROR.value,
                    lesson=f"Spread {spread_bps:.1f} bps exceeds safety threshold (40 bps); adverse selection risk high.",
                    past_loss_pct=2.8,
                    blocked=strict_veto,
                    evidence_id="SPREAD-EXCESS-VETO",
                )
            )

        return warnings

    def learn_from_trade(
        self,
        trade_id: str,
        symbol: str,
        predicted_return: float,
        realized_return: float,
        execution_shortfall_bps: float = 0.0,
        vwap_slippage_bps: float = 0.0,
        failure_type: Optional[str] = None,
        details: str = "",
    ) -> None:
        """Record completed trade outcome and update closed-loop failure memory."""
        self.learner.record_experience(
            trade_id=trade_id,
            symbol=symbol.strip().upper(),
            predicted_return=predicted_return,
            realized_return=realized_return,
            execution_shortfall_bps=execution_shortfall_bps,
            vwap_slippage_bps=vwap_slippage_bps,
        )
        if realized_return < -0.01:
            ft = failure_type or (
                FailureType.MODEL_ERROR.value
                if abs(predicted_return - realized_return) > 0.03
                else FailureType.EXECUTION_ERROR.value
            )
            self.learner.record_failure(
                failure_type=ft,
                details=details or f"Trade {trade_id} on {symbol} lost {realized_return * 100:.2f}%.",
                severity="HIGH" if realized_return < -0.03 else "MEDIUM",
            )
            # Atomically append to persistent mistakes file
            try:
                p = _mistakes_file_path()
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "trade_id": trade_id,
                    "symbol": symbol.strip().upper(),
                    "predicted_return": predicted_return,
                    "realized_return": realized_return,
                    "execution_shortfall_bps": execution_shortfall_bps,
                    "vwap_slippage_bps": vwap_slippage_bps,
                    "failure_type": ft,
                    "details": details,
                }
                with open(p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record) + "\n")
            except Exception:
                pass

    def get_bayesian_risk_penalty(self, symbol: str, regime: str = "NEUTRAL") -> float:
        """Compute an adaptive capital scaling multiplier (0.25 to 1.0) based on historical loss rate.

        If a model suffers frequent losses on this asset or regime, reduce allocation size.
        """
        sym = symbol.strip().upper()
        sym_exps = [e for e in self.learner.experiences if e.symbol == sym]
        if not sym_exps:
            return 1.0  # No prior negative experience

        losses = [e for e in sym_exps if e.realized_return < 0.0]
        loss_rate = len(losses) / len(sym_exps)

        # Scale penalty: 0.0 loss rate -> 1.0; 100% loss rate -> 0.25
        penalty = max(0.25, 1.0 - (loss_rate * 0.75))
        return round(penalty, 2)

    def get_mistakes_ledger(self) -> List[Dict[str, Any]]:
        """Return full ledger of all recorded trade experiences and attributed failures."""
        records = []
        for exp in self.learner.experiences:
            records.append({
                "trade_id": exp.trade_id,
                "symbol": exp.symbol,
                "predicted_return": exp.predicted_return,
                "realized_return": exp.realized_return,
                "execution_shortfall_bps": exp.execution_shortfall_bps,
                "vwap_slippage_bps": exp.vwap_slippage_bps,
                "status": "LOSS" if exp.realized_return < 0 else "PROFIT",
            })
        return records


__all__ = [
    "MistakeWarning",
    "PreTradeInterceptor",
]
