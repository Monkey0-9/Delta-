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
        # P0/A3: no fabricated bid/ask or sizes. Last price only from the
        # quote feed; depth renders UNAVAILABLE unless a real L2 source is
        # attached via store.viewmodels["quote_depth"|"depth_snapshot"].
        px: float | None = None
        chg, vwap, src = 0.0, 0.0, "unavailable"
        ok = False
        try:
            from delta_os.data_router import DataRouter

            q = DataRouter().quote(store.symbol, days=10)
            closes = q.frame["close"]
            px = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else px
            chg = (px / prev - 1.0) * 100.0 if prev else 0.0
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
                bid_sz=0, ask_sz=0, vwap=0.0, mode=store.mode.value,
                depth_source="unavailable")
        depth = (store.viewmodels.get("quote_depth")
                 or store.viewmodels.get("depth_snapshot") or {})
        if isinstance(depth, dict) and depth.get("bid") and depth.get("ask"):
            try:
                return QuoteVM(
                    symbol=store.symbol, last=Number(px, source=src),
                    change_pct=chg, bid=float(depth["bid"]), ask=float(depth["ask"]),
                    bid_sz=int(depth.get("bid_sz", 0)), ask_sz=int(depth.get("ask_sz", 0)),
                    vwap=vwap, mode=store.mode.value,
                    depth_source=str(depth.get("source", "live-l2")))
            except Exception:
                pass
        return QuoteVM(
            symbol=store.symbol, last=Number(px, source=src),
            change_pct=chg, bid=0.0, ask=0.0,
            bid_sz=0, ask_sz=0, vwap=vwap, mode=store.mode.value,
            depth_source="unavailable")

    def render_text(self, vm: QuoteVM) -> str:
        last_s = vm.last.render()
        depth_ok = (str(getattr(vm, "depth_source", "unavailable")).lower()
                    not in ("unavailable", "unknown", "")
                    and vm.bid > 0 and vm.ask > 0
                    and (vm.bid_sz > 0 or vm.ask_sz > 0))
        if "UNAVAILABLE" in last_s:
            return (f"{vm.symbol} [{vm.mode}] last {last_s} "
                    f"bid/ask UNAVAILABLE (no depth feed) [SOURCE/no-depth]  "
                    f"vwap UNAVAILABLE [SOURCE/no-feed]")
        if not depth_ok:
            return (f"{vm.symbol} [{vm.mode}] last {last_s} "
                    f"{vm.change_pct:+.2f}%  bid/ask UNAVAILABLE (no depth feed) "
                    f"[SOURCE/no-depth]  vwap {vm.vwap:.2f}")
        return (f"{vm.symbol} [{vm.mode}] last {last_s} "
                f"{vm.change_pct:+.2f}%  bid {vm.bid:.2f}x{vm.bid_sz}  "
                f"ask {vm.ask:.2f}x{vm.ask_sz}  vwap {vm.vwap:.2f} "
                f"[SOURCE/{vm.depth_source}]")


class BookScreen(BaseScreen):
    name = "book"

    def build_viewmodel(self, store: TerminalStore) -> BookVM:
        # A3: no fabricated depth. Levels only from an attached L2 source
        # (store.viewmodels["book_snapshot"|"depth_snapshot"]); else empty +
        # DEGRADED so render shows UNAVAILABLE (never size-0/spread-0 as if live).
        snap = (store.viewmodels.get("book_snapshot")
                or store.viewmodels.get("depth_snapshot") or {})
        if isinstance(snap, dict) and snap.get("bids") and snap.get("asks"):
            try:
                return BookVM(symbol=store.symbol,
                              bids=tuple(snap["bids"]), asks=tuple(snap["asks"]),
                              imbalance=float(snap.get("imbalance", 0.0)),
                              microprice=float(snap.get("microprice", 0.0)),
                              spread_bps=float(snap.get("spread_bps", 0.0)),
                              mode=store.mode.value,
                              source=str(snap.get("source", "live-l2")))
            except Exception:
                pass
        store.data_health = "DEGRADED"; store.data_live = False
        return BookVM(symbol=store.symbol, bids=(), asks=(),
                      imbalance=0.0, microprice=0.0,
                      spread_bps=0.0, mode=store.mode.value,
                      source="unavailable")

    def render_text(self, vm: BookVM) -> str:
        if not vm.bids:
            return (f"BOOK {vm.symbol} [{vm.mode}] UNAVAILABLE [SOURCE/no-l2] — "
                    f"no live depth")
        rows = [f"BOOK {vm.symbol} [{vm.mode}] imb {vm.imbalance:+.2f} spread {vm.spread_bps:.1f}bps [SOURCE/{vm.source}]"]
        for b, a in zip(vm.bids, vm.asks):
            rows.append(f"  {b['price']:.2f} x{b['size']:<6} | {a['price']:.2f} x{a['size']:<6}")
        return "\n".join(rows)


class ResearchScreen(BaseScreen):
    name = "research"

    def build_viewmodel(self, store: TerminalStore) -> ResearchVM:
        # A3: no invented IDs. Only a real experiment attached via
        # store.publish("research", ResearchVM(...)) renders; store field
        # defaults (H-2026-0041/EXP-9182/...) are never used as display truth.
        vm = store.viewmodels.get("research")
        if vm is not None:
            return vm
        return ResearchVM(experiment_id="", hypothesis="", stage="UNAVAILABLE",
                          mode=store.mode.value, source="unavailable")

    def render_text(self, vm: ResearchVM) -> str:
        if not vm.experiment_id:
            return (f"RESEARCH [{vm.mode}] UNAVAILABLE [SOURCE/no-experiment] — "
                    f"no experiment attached (no invented IDs)")
        src = getattr(vm, "source", "") or "research-registry"
        return "\n".join([
            f"RESEARCH [{vm.mode}] [SOURCE/{src}]",
            "",
            f"Hypothesis: {vm.hypothesis}",
            f"Experiment: {vm.experiment_id}",
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
        # A3: portfolio only from an attached source
        # (store.viewmodels["portfolio_snapshot"]); no-source renders
        # UNAVAILABLE (None), never $0 as if safe. An attached source that
        # genuinely reports zero still renders $0 (attached-empty vs no-source).
        snap = store.viewmodels.get("portfolio_snapshot") or {}
        if isinstance(snap, dict) and all(
                k in snap and snap[k] is not None
                for k in ("net_liq", "cash", "gross_pct", "net_pct", "beta")):
            return PortfolioVM(net_liq=snap.get("net_liq"),
                               cash=snap.get("cash"),
                               gross_pct=snap.get("gross_pct"),
                               net_pct=snap.get("net_pct"),
                               beta=snap.get("beta"),
                               positions=tuple(snap.get("positions", ())),
                               mode=store.mode.value,
                               live=(store.mode.value == "LIVE"),
                               source=str(snap.get("source", "portfolio-engine")))
        return PortfolioVM(net_liq=None, cash=None,
                           gross_pct=None, net_pct=None, beta=None,
                           positions=(), mode=store.mode.value,
                           live=False, source="unavailable")

    def render_text(self, vm: PortfolioVM) -> str:
        if any(v is None for v in (vm.net_liq, vm.cash, vm.gross_pct,
                                   vm.net_pct, vm.beta)):
            return (f"PORTFOLIO [{vm.mode}] UNAVAILABLE [SOURCE/no-portfolio] — "
                    f"no engine/portfolio source attached")
        tag = "LIVE STATE" if vm.live else f"{vm.mode} — {'illustrative' if vm.mode=='DEMO' else 'paper/sim state'}"
        return (f"PORTFOLIO [{tag}] NLV ${vm.net_liq:,.0f} cash ${vm.cash:,.0f} "
                f"gross {vm.gross_pct:.1f}% net {vm.net_pct:.1f}% beta {vm.beta:.2f} "
                f"[SOURCE/{vm.source}]")


class RiskScreen(BaseScreen):
    name = "risk"

    def build_viewmodel(self, store: TerminalStore) -> RiskVM:
        status = store.risk_state or "SAFE"
        # Normalize to GREEN/YELLOW/RED display while preserving SAFE/REVIEW/BLOCKED semantics
        display = {"SAFE": "GREEN", "REVIEW": "YELLOW", "BLOCKED": "RED"}.get(status.upper(), "GREEN")
        # A3: risk metrics only from an attached source
        # (store.viewmodels["risk_snapshot"]); no-source renders UNAVAILABLE
        # (None), never 0.00% as if safe.
        snap = store.viewmodels.get("risk_snapshot") or {}
        if isinstance(snap, dict) and all(
                k in snap and snap[k] is not None
                for k in ("gross", "net", "var99", "es99")):
            return RiskVM(status=str(snap.get("status", display)),
                          gross=snap.get("gross"), net=snap.get("net"),
                          var99=snap.get("var99"), es99=snap.get("es99"),
                          watches=tuple(snap.get("watches", ())),
                          mode=store.mode.value,
                          source=str(snap.get("source", "risk-engine")))
        return RiskVM(status=display, gross=None, net=None,
                      var99=None, es99=None,
                      watches=("UNAVAILABLE:no-risk-engine",),
                      mode=store.mode.value, source="unavailable")

    def render_text(self, vm: RiskVM) -> str:
        if any(v is None for v in (vm.gross, vm.net, vm.var99, vm.es99)):
            return (f"RISK [{vm.mode}] {vm.status} UNAVAILABLE [SOURCE/no-risk-engine] — "
                    f"no risk engine source attached "
                    f"Ctrl+X K kill-switch · research stays available")
        return (f"RISK [{vm.mode}] {vm.status} gross {vm.gross:.0f}/{vm.gross_lim:.0f} "
                f"net {vm.net:.0f}/{vm.net_lim:.0f} VaR99 {vm.var99:.2f}% ES99 {vm.es99:.2f}% "
                f"[SOURCE/{vm.source}] "
                f"Ctrl+X K kill-switch · research stays available")
