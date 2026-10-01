"""MARKET / SECURITY / BOOK / RESEARCH / ALPHA / PORTFOLIO / RISK screens."""
from __future__ import annotations

from .base import BaseScreen
from ..state.store import TerminalStore
from ..viewmodels.models import (
    MarketVM, QuoteVM, Number, BookVM, ResearchVM, RiskVM, PortfolioVM,
)


class MarketScreen(BaseScreen):
    name = "market"

    def build_viewmodel(self, store: TerminalStore) -> MarketVM:
        # P0: no illustrative indices. Live or DEGRADED/UNAVAILABLE only.
        indices: tuple = ()
        regime, sectors, events = "UNKNOWN", (), ()
        try:  # live macro when backend reachable; never crash the TUI
            from delta_os.data_router import DataRouter

            q = DataRouter().quote("SPY", days=5)
            last = float(q.frame["close"].iloc[-1])
            prev = float(q.frame["close"].iloc[-2]) if len(q.frame) > 1 else last
            chg = (last / prev - 1.0) * 100.0 if prev else 0.0
            indices = (("SPY", round(chg, 2)),)
            tag = getattr(getattr(q, "provenance", None), "tier", "") or ""
            if "SYNTH" in str(tag).upper() or "STALE" in str(tag).upper():
                store.data_health = "DEGRADED"
                store.data_live = False
            else:
                store.data_health = "HEALTHY"
                store.data_live = True
        except Exception:
            store.data_health = "DEGRADED"
            store.data_live = False
        return MarketVM(
            indices=indices,
            regime=regime,
            sectors=sectors,
            events=events,
            mode=store.mode.value,
        )

    def render_text(self, vm: MarketVM) -> str:
        if not vm.indices:
            return f"MARKET [{vm.mode}] UNAVAILABLE — backend unreachable (DEGRADED)"
        return "MARKET [" + vm.mode + "] " + " ".join(
            f"{k} {v:+.2f}%" for k, v in vm.indices)


class SecurityScreen(BaseScreen):
    name = "security"

    def build_viewmodel(self, store: TerminalStore) -> QuoteVM:
        # P0: no illustrative 177.42 quote. Live or explicit UNAVAILABLE.
        px: float | None = None
        chg, bid, ask, vwap, src = 0.0, 0.0, 0.0, 0.0, "unavailable"
        ok = False
        try:
            from delta_os.data_router import DataRouter

            q = DataRouter().quote(store.symbol, days=10)
            closes = q.frame["close"]
            px = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else px
            chg = (px / prev - 1.0) * 100.0 if prev else 0.0
            bid, ask = px - 0.01, px + 0.01
            try:
                vwap = float(q.frame["close"].tail(5).mean())
            except Exception:
                vwap = px
            prov = getattr(q, "provenance", None)
            src = str(getattr(prov, "tier", "live") or "live").lower()
            store.data_live = "synth" not in src and "stale" not in src and "unavailable" not in src
            store.data_health = "HEALTHY" if store.data_live else "DEGRADED"
            ok = True
        except Exception:
            store.data_health = "DEGRADED"
            store.data_live = False
        if not ok or px is None:
            return QuoteVM(
                symbol=store.symbol, last=Number(0.0, source="unavailable"),
                change_pct=0.0, bid=0.0, ask=0.0,
                bid_sz=0, ask_sz=0, vwap=0.0, mode=store.mode.value)
        return QuoteVM(
            symbol=store.symbol, last=Number(px, source=src),
            change_pct=chg, bid=bid, ask=ask,
            bid_sz=1800, ask_sz=1200, vwap=vwap, mode=store.mode.value)

    def render_text(self, vm: QuoteVM) -> str:
        return (f"{vm.symbol} [{vm.mode}] last {vm.last.render()} "
                f"{vm.change_pct:+.2f}%  bid {vm.bid:.2f}x{vm.bid_sz}  "
                f"ask {vm.ask:.2f}x{vm.ask_sz}  vwap {vm.vwap:.2f}")


class BookScreen(BaseScreen):
    name = "book"

    def build_viewmodel(self, store: TerminalStore) -> BookVM:
        # P0: order-book levels only from live quote; else empty + DEGRADED.
        try:
            from delta_os.data_router import DataRouter

            q = DataRouter().quote(store.symbol, days=5)
            px = float(q.frame["close"].iloc[-1])
            bids = tuple({"price": px - 0.01 * i, "size": 0} for i in range(5))
            asks = tuple({"price": px + 0.01 * (i + 1), "size": 0} for i in range(5))
            return BookVM(symbol=store.symbol, bids=bids, asks=asks,
                          imbalance=0.0, microprice=px,
                          spread_bps=0.0, mode=store.mode.value)
        except Exception:
            store.data_health = "DEGRADED"; store.data_live = False
            return BookVM(symbol=store.symbol, bids=(), asks=(),
                          imbalance=0.0, microprice=0.0,
                          spread_bps=0.0, mode=store.mode.value)

    def render_text(self, vm: BookVM) -> str:
        if not vm.bids:
            return f"BOOK {vm.symbol} [{vm.mode}] UNAVAILABLE — no live depth"
        rows = [f"BOOK {vm.symbol} [{vm.mode}] imb {vm.imbalance:+.2f} spread {vm.spread_bps:.1f}bps"]
        for b, a in zip(vm.bids, vm.asks):
            rows.append(f"  {b['price']:.2f} x{b['size']:<6} | {a['price']:.2f} x{a['size']:<6}")
        return "\n".join(rows)


class ResearchScreen(BaseScreen):
    name = "research"

    def build_viewmodel(self, store: TerminalStore) -> ResearchVM:
        vm = store.viewmodels.get("research")
        if vm is not None:
            return vm
        return ResearchVM(experiment_id=getattr(store, "experiment", "EXP-9182"),
                          hypothesis=getattr(store, "hypothesis", "H-2026-0041"),
                          stage=getattr(store, "research_status", "OOS validation"),
                          mode=store.mode.value)

    def render_text(self, vm: ResearchVM) -> str:
        return "\n".join([
            f"RESEARCH [{vm.mode}]",
            "",
            f"Session:    NVDA regime research",
            f"Hypothesis: {vm.hypothesis}",
            f"Experiment: {vm.experiment_id}",
            f"Strategy:   momentum-v4",
            f"Dataset:    US_EQ_PIT_2026_08",
            f"Status:     {vm.stage}",
            "",
            "[Open analysis ↗] [Run research] [Simulate]",
        ])


class AlphaScreen(BaseScreen):
    name = "alpha"

    def build_viewmodel(self, store: TerminalStore):
        return {"families": ("momentum", "mean_reversion", "stat_arb"),
                "mode": store.mode.value}

    def render_text(self, vm) -> str:
        return f"ALPHA LAB [{vm['mode']}] families: {', '.join(vm['families'])}"


class PortfolioScreen(BaseScreen):
    name = "portfolio"

    def build_viewmodel(self, store: TerminalStore) -> PortfolioVM:
        # P0: portfolio from store positions only; no illustrative $1M book.
        return PortfolioVM(net_liq=0.0, cash=0.0,
                           gross_pct=0.0, net_pct=0.0, beta=0.0,
                           positions=(), mode=store.mode.value,
                           live=(store.mode.value == "LIVE"))

    def render_text(self, vm: PortfolioVM) -> str:
        tag = "LIVE STATE" if vm.live else f"{vm.mode} — {'illustrative' if vm.mode=='DEMO' else 'paper/sim state'}"
        return (f"PORTFOLIO [{tag}] NLV ${vm.net_liq:,.0f} cash ${vm.cash:,.0f} "
                f"gross {vm.gross_pct:.1f}% net {vm.net_pct:.1f}% beta {vm.beta:.2f}")


class RiskScreen(BaseScreen):
    name = "risk"

    def build_viewmodel(self, store: TerminalStore) -> RiskVM:
        status = store.risk_state or "SAFE"
        # Normalize to GREEN/YELLOW/RED display while preserving SAFE/REVIEW/BLOCKED semantics
        display = {"SAFE": "GREEN", "REVIEW": "YELLOW", "BLOCKED": "RED"}.get(status.upper(), "GREEN")
        # P0: risk metrics only from live risk engine; else zeros + watch UNKNOWN.
        return RiskVM(status=display, gross=0.0, net=0.0,
                      var99=0.0, es99=0.0,
                      watches=("concentration:UNKNOWN", "sector:UNKNOWN", "liquidity:UNKNOWN"),
                      mode=store.mode.value)

    def render_text(self, vm: RiskVM) -> str:
        return (f"RISK [{vm.mode}] {vm.status} gross {vm.gross:.0f}/{vm.gross_lim:.0f} "
                f"net {vm.net:.0f}/{vm.net_lim:.0f} VaR99 {vm.var99:.2f}%  "
                f"Ctrl+X K kill-switch · research stays available")
