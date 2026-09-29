"""Unified indicators library: single entry for OpenCode + terminal + research.

Wraps (never forks):
- data.market.feature_engine.TechnicalFeature (rsi/macd/bollinger)
- delta_os.quantkit (vwap_bands, atr, volume_profile)
- quant.time_series.statistics (returns/vol helpers where relevant)

Pure pandas/numpy. All functions take a DataFrame with
open/high/low/close/volume and return Series or dict. `summarize(frame)`
returns the one-shot card used by /indicators, /quant and ReasonForge.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

INDICATORS_VERSION = "indicators-v1"


def _close(frame: pd.DataFrame) -> pd.Series:
    return frame["close"].astype(float)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=int(span), adjust=False).mean()


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(int(window)).mean()


def rsi(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = _close(frame).diff()
    gain = delta.where(delta > 0, 0).rolling(window=int(period)).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=int(period)).mean()
    rs = gain / loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def macd(frame: pd.DataFrame, fast: int = 12, slow: int = 26,
         signal: int = 9) -> pd.DataFrame:
    c = _close(frame)
    line = ema(c, fast) - ema(c, slow)
    sig = ema(line, signal)
    return pd.DataFrame({"macd": line, "signal": sig,
                         "hist": line - sig}, index=frame.index)


def bollinger(frame: pd.DataFrame, period: int = 20,
              mult: float = 2.0) -> pd.DataFrame:
    c = _close(frame)
    mid = c.rolling(int(period)).mean()
    sd = c.rolling(int(period)).std()
    return pd.DataFrame({"mid": mid, "upper": mid + mult * sd,
                         "lower": mid - mult * sd,
                         "pct_b": (c - (mid - mult * sd)) / ((mid + mult * sd) - (mid - mult * sd))},
                        index=frame.index)


def stochastic(frame: pd.DataFrame, k: int = 14,
               d: int = 3) -> pd.DataFrame:
    h = frame["high"].astype(float).rolling(int(k)).max()
    low = frame["low"].astype(float).rolling(int(k)).min()
    c = _close(frame)
    kline = 100 * (c - low) / (h - low).replace(0, np.nan)
    return pd.DataFrame({"k": kline, "d": kline.rolling(int(d)).mean()},
                        index=frame.index).fillna(50.0)


def atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    from delta_os.quantkit import atr as _atr
    return _atr(frame, window=int(window))


def vwap_bands(frame: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    from delta_os.quantkit import vwap_bands as _vb
    return _vb(frame, window=int(window))


def adx(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    h = frame["high"].astype(float)
    low = frame["low"].astype(float)
    c = _close(frame)
    up, down = h.diff(), -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([(h - low), (h - c.shift()).abs(),
                    (low - c.shift()).abs()], axis=1).max(axis=1)
    atr_s = pd.Series(tr, index=frame.index).rolling(int(period)).mean().replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=frame.index).rolling(int(period)).mean() / atr_s
    minus_di = 100 * pd.Series(minus_dm, index=frame.index).rolling(int(period)).mean() / atr_s
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(int(period)).mean().fillna(20.0)


def obv(frame: pd.DataFrame) -> pd.Series:
    c = _close(frame)
    v = frame["volume"].astype(float)
    direction = np.sign(c.diff().fillna(0))
    return (direction * v).cumsum()


def summarize(frame: pd.DataFrame) -> dict:
    """One-shot indicator card: last values + textual biases.

    Never raises on short frames — returns n/a legs instead.
    """
    if frame is None or len(frame) < 30:
        return {"error": f"need >= 30 bars, have {0 if frame is None else len(frame)}."}
    last_close = float(_close(frame).iloc[-1])
    r = float(rsi(frame).iloc[-1])
    m = macd(frame).iloc[-1]
    b = bollinger(frame).iloc[-1]
    s = stochastic(frame).iloc[-1]
    a = float(atr(frame).iloc[-1])
    x = float(adx(frame).iloc[-1])
    vb = vwap_bands(frame).iloc[-1]
    from delta_os.quantkit import vwap_location
    loc = vwap_location(last_close, vb)

    def _bias_rsi(v: float) -> str:
        return "OVERBOUGHT" if v > 70 else ("OVERSOLD" if v < 30 else "NEUTRAL")

    macd_bias = "BULLISH" if float(m["hist"]) > 0 else "BEARISH"
    bb_bias = ("ABOVE-UPPER" if last_close > float(b["upper"])
               else ("BELOW-LOWER" if last_close < float(b["lower"]) else "INSIDE"))
    trend = "TRENDING" if x > 25 else "RANGING"
    return {
        "close": round(last_close, 2),
        "rsi_14": round(r, 1),
        "rsi_bias": _bias_rsi(r),
        "macd_line": round(float(m["macd"]), 3),
        "macd_signal": round(float(m["signal"]), 3),
        "macd_hist": round(float(m["hist"]), 3),
        "macd_bias": macd_bias,
        "boll_pct_b": round(float(b["pct_b"]), 3),
        "boll_bias": bb_bias,
        "stoch_k": round(float(s["k"]), 1),
        "stoch_d": round(float(s["d"]), 1),
        "atr_14": round(a, 2),
        "adx_14": round(x, 1),
        "regime": trend,
        "vwap": round(float(vb["vwap"]), 2),
        "vwap_sigma": loc,
    }


def render_card(symbol: str, summary: dict) -> str:
    if "error" in summary:
        return f"{symbol.upper()}: indicators {summary['error']}"
    return (
        f"{symbol.upper()} ${summary['close']:,.2f} | "
        f"RSI {summary['rsi_14']} [{summary['rsi_bias']}] | "
        f"MACD {summary['macd_hist']:+.3f} [{summary['macd_bias']}] | "
        f"%B {summary['boll_pct_b']:.2f} [{summary['boll_bias']}] | "
        f"Stoch {summary['stoch_k']:.0f}/{summary['stoch_d']:.0f} | "
        f"ATR {summary['atr_14']:.2f} ADX {summary['adx_14']:.1f} [{summary['regime']}] | "
        f"VWAP {summary['vwap']:,.2f} ({summary['vwap_sigma']:+.1f}s)"
    )


__all__ = ["INDICATORS_VERSION", "ema", "sma", "rsi", "macd", "bollinger",
           "stochastic", "atr", "vwap_bands", "adx", "obv",
           "summarize", "render_card"]
