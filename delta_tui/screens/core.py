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
        return MarketVM(
            indices=(("SPX", 0.74), ("NASDAQ", 1.03), ("VIX", 17.4)),
            regime="NEUTRAL",
            sectors=(("TECH", 1.8), ("ENERGY", 0.4), ("FIN", 0.9)),
            events=(("09:30", "OPEN"), ("16:00", "CLOSE")),
            mode=store.mode.value,
        )

    def render_text(self, vm: MarketVM) -> str:
        return "MARKET [" + vm.mode + "] " + " ".join(
            f"{k} {v:+.2f}%" for k, v in vm.indices)


class SecurityScreen(BaseScreen):
    name = "security"

    def build_viewmodel(self, store: TerminalStore) -> QuoteVM:
        px = 177.42
        return QuoteVM(
            symbol=store.symbol, last=Number(px, source="yahoo"),
            change_pct=1.82, bid=px - 0.01, ask=px + 0.01,
            bid_sz=1800, ask_sz=1200, vwap=176.91, mode=store.mode.value)

    def render_text(self, vm: QuoteVM) -> str:
        return (f"{vm.symbol} [{vm.mode}] last {vm.last.render()} "
                f"{vm.change_pct:+.2f}%  bid {vm.bid:.2f}x{vm.bid_sz}  "
                f"ask {vm.ask:.2f}x{vm.ask_sz}  vwap {vm.vwap:.2f}")


class BookScreen(BaseScreen):
    name = "book"

    def build_viewmodel(self, store: TerminalStore) -> BookVM:
        px = 177.42
        bids = tuple({"price": px - 0.01 * i, "size": 1800 + i * 2000} for i in range(5))
        asks = tuple({"price": px + 0.01 * (i + 1), "size": 1200 + i * 1800} for i in range(5))
        return BookVM(symbol=store.symbol, bids=bids, asks=asks,
                      imbalance=0.21, microprice=px + 0.001,
                      spread_bps=2.0, mode=store.mode.value)

    def render_text(self, vm: BookVM) -> str:
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
        return ResearchVM(experiment_id="EXP-LOCAL", hypothesis="pending",
                          stage="planned", mode="RESEARCH")

    def render_text(self, vm: ResearchVM) -> str:
        return (f"RESEARCH {vm.experiment_id} [{vm.mode}]\n"
                f"hypothesis: {vm.hypothesis}\nstage: {vm.stage} "
                f"verdict: {vm.verdict}")


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
        return PortfolioVM(net_liq=1_024_218.0, cash=320_118.0,
                           gross_pct=143.2, net_pct=37.6, beta=0.71,
                           positions=(), mode=store.mode.value,
                           live=(store.mode.value == "LIVE"))

    def render_text(self, vm: PortfolioVM) -> str:
        tag = "LIVE STATE" if vm.live else f"{vm.mode} — {'illustrative' if vm.mode=='DEMO' else 'paper/sim state'}"
        return (f"PORTFOLIO [{tag}] NLV ${vm.net_liq:,.0f} cash ${vm.cash:,.0f} "
                f"gross {vm.gross_pct:.1f}% net {vm.net_pct:.1f}% beta {vm.beta:.2f}")


class RiskScreen(BaseScreen):
    name = "risk"

    def build_viewmodel(self, store: TerminalStore) -> RiskVM:
        return RiskVM(status="GREEN", gross=143.0, net=37.0,
                      var99=2.14, es99=3.31,
                      watches=("concentration:OK", "sector:OK", "liquidity:OK"),
                      mode=store.mode.value)

    def render_text(self, vm: RiskVM) -> str:
        return (f"RISK [{vm.mode}] {vm.status} gross {vm.gross:.0f}/{vm.gross_lim:.0f} "
                f"net {vm.net:.0f}/{vm.net_lim:.0f} VaR99 {vm.var99:.2f}%")
