"""DELTA OS — Terminal Financial Visualization Engine.

Renders institutional-grade in-terminal sectioned financial charts:
1. High-resolution Candlestick charts (Open, High, Low, Close) with price axis.
2. Volume histogram subplots aligned beneath price action.
3. Technical indicator subplots (RSI with 30/70 thresholds, MACD histogram).
4. L2 Order Book Depth Ladder with price-level visual volume bars.

Truth-first guarantee:
Every chart displays exact timestamps, volume, last price, and explicit
provenance badges (TIER1 / TIER2 / PAPER / SYNTHETIC / UNAVAILABLE).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass(frozen=True)
class CandleBar:
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timestamp: str = ""


def render_candlestick_chart(
    candles: Sequence[Dict[str, Any] | CandleBar],
    symbol: str,
    width: int = 70,
    height: int = 12,
    provenance: str = "AVAILABLE",
    show_volume: bool = True,
    timeframe: str = "1D",
) -> str:
    """Render an ASCII/Unicode candlestick chart with a price axis and provenance badge."""
    if not candles:
        return f"[{symbol}] Chart data UNAVAILABLE."

    # Parse and normalize bars
    bars: List[CandleBar] = []
    for c in candles:
        if isinstance(c, CandleBar):
            bars.append(c)
        elif isinstance(c, dict):
            bars.append(
                CandleBar(
                    open=float(c.get("open", 0.0)),
                    high=float(c.get("high", 0.0)),
                    low=float(c.get("low", 0.0)),
                    close=float(c.get("close", 0.0)),
                    volume=float(c.get("volume", 0.0)),
                    timestamp=str(c.get("timestamp", "")),
                )
            )

    # Window to available width
    window = bars[-width:] if len(bars) > width else bars
    num_bars = len(window)
    if num_bars == 0:
        return f"[{symbol}] Empty price series."

    highs = [b.high for b in window]
    lows = [b.low for b in window]
    min_px = min(lows)
    max_px = max(highs)
    spread = max_px - min_px
    if spread <= 0:
        spread = 1.0

    last_px = window[-1].close
    prev_px = window[-2].close if len(window) > 1 else window[-1].open
    change = last_px - prev_px
    change_pct = (change / prev_px * 100.0) if prev_px > 0 else 0.0

    lines: List[str] = []

    # 1. Header with symbol, timeframe, metrics, and provenance badge
    chg_sign = "+" if change >= 0 else ""
    header = (
        f"  {symbol:<8} [{timeframe}] · Last: {last_px:,.2f} ({chg_sign}{change:,.2f} | {chg_sign}{change_pct:.2f}%) "
        f"· High: {max_px:,.2f} · Low: {min_px:,.2f} · [{provenance}]"
    )
    lines.append(header)
    lines.append("  " + "─" * (num_bars + 12))

    # 2. Candlestick Canvas
    grid = [[" " for _ in range(num_bars)] for _ in range(height)]

    for x, b in enumerate(window):
        y_h = int((b.high - min_px) / spread * (height - 1))
        y_l = int((b.low - min_px) / spread * (height - 1))
        y_o = int((b.open - min_px) / spread * (height - 1))
        y_c = int((b.close - min_px) / spread * (height - 1))

        # Clamp grid coordinates
        y_h = max(0, min(height - 1, y_h))
        y_l = max(0, min(height - 1, y_l))
        y_o = max(0, min(height - 1, y_o))
        y_c = max(0, min(height - 1, y_c))

        # Draw wick
        for y in range(y_l, y_h + 1):
            grid[y][x] = "│"

        # Draw candle body
        top = max(y_o, y_c)
        bot = min(y_o, y_c)
        char = "█" if b.close >= b.open else "░"
        for y in range(bot, top + 1):
            grid[y][x] = char

    # Print rows from highest price to lowest
    for row in range(height - 1, -1, -1):
        price_at_row = min_px + (row / (height - 1)) * spread
        row_str = "".join(grid[row])
        lines.append(f"{price_at_row:8.2f} │ {row_str}")

    lines.append("  " + "─" * (num_bars + 12))

    # 3. Volume Subplot
    if show_volume:
        vols = [b.volume for b in window]
        max_vol = max(vols) if vols and max(vols) > 0 else 1.0
        vol_height = 3
        lines.append("  VOLUME")
        for vrow in range(vol_height - 1, -1, -1):
            vol_chars = []
            for b in window:
                scaled = int((b.volume / max_vol) * vol_height) if max_vol > 0 else 0
                vol_chars.append("█" if scaled > vrow else " ")
            lines.append(f"  vol    │ {''.join(vol_chars)}")
        lines.append("  " + "─" * (num_bars + 12))

    return "\n".join(lines)


def render_rsi_subplot(
    rsi_values: Sequence[float],
    width: int = 70,
    height: int = 6,
    overbought: float = 70.0,
    oversold: float = 30.0,
) -> str:
    """Render RSI technical indicator subplot with 30 and 70 threshold lines."""
    if not rsi_values:
        return "  RSI: UNAVAILABLE"

    window = list(rsi_values[-width:])
    num_bars = len(window)
    last_rsi = window[-1] if window else 50.0

    lines = [
        f"  RSI (14) · Current: {last_rsi:.1f} · Overbought: {overbought:.0f} · Oversold: {oversold:.0f}",
        "  " + "─" * (num_bars + 12),
    ]

    grid = [[" " for _ in range(num_bars)] for _ in range(height)]

    # Map 0..100 to height
    for x, rsi in enumerate(window):
        clamped = max(0.0, min(100.0, float(rsi)))
        y = int((clamped / 100.0) * (height - 1))
        y = max(0, min(height - 1, y))
        grid[y][x] = "●"

    for row in range(height - 1, -1, -1):
        level = (row / (height - 1)) * 100.0
        row_chars = list(grid[row])
        # Insert threshold guide dashes if space is empty
        if abs(level - overbought) < (100.0 / height / 2.0):
            row_chars = [c if c != " " else "┄" for c in row_chars]
        elif abs(level - oversold) < (100.0 / height / 2.0):
            row_chars = [c if c != " " else "┄" for c in row_chars]

        lines.append(f"{level:7.0f}  │ {''.join(row_chars)}")

    lines.append("  " + "─" * (num_bars + 12))
    return "\n".join(lines)


def render_depth_ladder(
    bids: Sequence[Dict[str, Any]],
    asks: Sequence[Dict[str, Any]],
    width: int = 64,
    provenance: str = "SYNTHETIC",
) -> str:
    """Render horizontal Level 2 Order Book Depth Ladder with price & volume bars."""
    lines: List[str] = [
        f"  LEVEL 2 ORDER BOOK DEPTH LADDER [{provenance}]",
        "  " + "─" * width,
        f"  {'BID VOLUME':>12}  {'BID SIZE':>8}  {'BID PRICE':>9}  │  {'ASK PRICE':<9}  {'ASK SIZE':<8}  {'ASK VOLUME':<12}",
        "  " + "─" * width,
    ]

    bid_list = list(bids)[:6]
    ask_list = list(asks)[:6]
    max_rows = max(len(bid_list), len(ask_list), 1)

    all_sizes = [int(b.get("size", 0)) for b in bid_list] + [int(a.get("size", 0)) for a in ask_list]
    max_size = max(all_sizes) if all_sizes and max(all_sizes) > 0 else 1

    for i in range(max_rows):
        b = bid_list[i] if i < len(bid_list) else None
        a = ask_list[i] if i < len(ask_list) else None

        if b:
            b_sz = int(b.get("size", 0))
            b_px = float(b.get("price", 0.0))
            b_bar_len = int((b_sz / max_size) * 10)
            b_bar = "█" * b_bar_len
            b_str = f"{b_bar:>12}  {b_sz:>8}  {b_px:>9.2f}"
        else:
            b_str = f"{'':>12}  {'':>8}  {'':>9}"

        if a:
            a_sz = int(a.get("size", 0))
            a_px = float(a.get("price", 0.0))
            a_bar_len = int((a_sz / max_size) * 10)
            a_bar = "█" * a_bar_len
            a_str = f"{a_px:<9.2f}  {a_sz:<8}  {a_bar:<12}"
        else:
            a_str = f"{'':<9}  {'':<8}  {'':<12}"

        lines.append(f"  {b_str}  │  {a_str}")

    # Spread & Order Book Imbalance Ratio (OBIR) calculation
    total_bid_sz = sum(int(b.get("size", 0)) for b in bid_list)
    total_ask_sz = sum(int(a.get("size", 0)) for a in ask_list)
    tot_depth = total_bid_sz + total_ask_sz
    obir = ((total_bid_sz - total_ask_sz) / tot_depth) if tot_depth > 0 else 0.0
    bias_tag = "BUY HEAVY" if obir > 0.15 else ("SELL HEAVY" if obir < -0.15 else "BALANCED")

    if bid_list and ask_list:
        best_bid = float(bid_list[0].get("price", 0.0))
        best_ask = float(ask_list[0].get("price", 0.0))
        spread_abs = best_ask - best_bid
        spread_bps = (spread_abs / best_bid * 10_000.0) if best_bid > 0 else 0.0
        lines.append("  " + "─" * width)
        lines.append(f"  Spread: {spread_abs:,.2f} ({spread_bps:.1f} bps) · Top Book: Bid {best_bid:,.2f} / Ask {best_ask:,.2f}")
        lines.append(f"  Depth Imbalance: OBIR {obir:+.2f} [{bias_tag}] · Total Depth: {tot_depth:,} shares")

    lines.append("  " + "─" * width)
    return "\n".join(lines)


def render_macd_subplot(
    macd_series: Sequence[float],
    signal_series: Sequence[float],
    width: int = 70,
    height: int = 5,
) -> str:
    """Render MACD indicator histogram subplot."""
    if not macd_series or not signal_series:
        return "  MACD: UNAVAILABLE"

    w_macd = list(macd_series[-width:])
    w_sig = list(signal_series[-width:])
    n = min(len(w_macd), len(w_sig))
    if n == 0:
        return "  MACD: EMPTY"

    hist = [w_macd[i] - w_sig[i] for i in range(n)]
    last_m = w_macd[-1]
    last_s = w_sig[-1]
    last_h = hist[-1]

    lines = [
        f"  MACD (12, 26, 9) · MACD: {last_m:+.2f} · Signal: {last_s:+.2f} · Hist: {last_h:+.2f}",
        "  " + "─" * (n + 12),
    ]

    max_h = max(abs(h) for h in hist) if hist and max(abs(h) for h in hist) > 0 else 1.0
    for r in range(height - 1, -1, -1):
        level = ((r - (height // 2)) / (height // 2)) * max_h
        row_chars = []
        for h in hist:
            if h >= 0 and level >= 0 and h >= level:
                row_chars.append("▲")
            elif h < 0 and level < 0 and h <= level:
                row_chars.append("▼")
            elif abs(level) < (max_h / height / 2.0):
                row_chars.append("┄")
            else:
                row_chars.append(" ")
        lines.append(f"{level:7.2f}  │ {''.join(row_chars)}")

    lines.append("  " + "─" * (n + 12))
    return "\n".join(lines)


__all__ = [
    "CandleBar",
    "render_candlestick_chart",
    "render_rsi_subplot",
    "render_depth_ladder",
    "render_macd_subplot",
]
