"""Global instrument resolution layer (terminal redesign Phase 3).

Complements the tri-temporal SecurityMaster: a ticker is NOT a security.
Ambiguous input is never guessed — AmbiguousInstrument carries candidates
for the MUST-show selection UI. Broker symbol mapping is a SEPARATE
component (BrokerSymbolMapper).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GlobalInstrument:
    instrument_id: str  # canonical, e.g. EQ-RELIANCE-NSE
    asset_class: str = "equity"  # equity|etf|index|future|option|bond|fx|crypto
    legal_name: str = ""
    ticker: str = ""
    exchange: str = ""
    mic: str = ""
    country: str = ""
    currency: str = ""
    isin: str = ""
    figi: str = ""
    local_symbol: str = ""
    timezone: str = "UTC"
    status: str = "listed"


_SEED: list[GlobalInstrument] = [
    GlobalInstrument("EQ-RELIANCE-NSE", "equity", "Reliance Industries Ltd", "RELIANCE",
                     "NSE", "XNSE", "IN", "INR", "IN00000000", "", "RELIANCE",
                     "Asia/Kolkata", "listed"),
    GlobalInstrument("EQ-AAPL-XNAS", "equity", "Apple Inc", "AAPL",
                     "NASDAQ", "XNAS", "US", "USD", "US00000000", "", "AAPL",
                     "America/New_York", "listed"),
    GlobalInstrument("EQ-NVDA-XNAS", "equity", "NVIDIA Corp", "NVDA",
                     "NASDAQ", "XNAS", "US", "USD", "US00000000", "", "NVDA",
                     "America/New_York", "listed"),
    GlobalInstrument("EQ-ABC-NYSE", "equity", "ABC Corp (TEST)", "ABC",
                     "NYSE", "XNYS", "US", "USD", "", "", "ABC",
                     "America/New_York", "listed"),
    GlobalInstrument("EQ-ABC-LSE", "equity", "ABC Plc (TEST)", "ABC",
                     "LSE", "XLON", "GB", "GBP", "", "", "ABC",
                     "Europe/London", "listed"),
    GlobalInstrument("EQ-ABC-TSE", "equity", "ABC KK (TEST)", "ABC",
                     "TSE", "XTKS", "JP", "JPY", "", "", "ABC",
                     "Asia/Tokyo", "listed"),
]


class AmbiguousInstrument(Exception):
    def __init__(self, candidates: list[GlobalInstrument]):
        self.candidates = candidates
        super().__init__(f"MULTIPLE INSTRUMENTS FOUND ({len(candidates)})")


class UnknownInstrument(Exception):
    pass


class GlobalResolver:
    """Ticker -> canonical instrument. Never guesses on ambiguity."""

    def __init__(self, instruments: list[GlobalInstrument] | None = None):
        self._by_ticker: dict[str, list[GlobalInstrument]] = {}
        for ins in (instruments or list(_SEED)):
            self._by_ticker.setdefault(ins.ticker.upper(), []).append(ins)

    def resolve(self, text: str) -> GlobalInstrument:
        listed = [c for c in self._by_ticker.get((text or "").strip().upper(), [])
                  if c.status == "listed"]
        if not listed:
            raise UnknownInstrument(f"unknown instrument {text!r} — execution blocked")
        if len(listed) > 1:
            raise AmbiguousInstrument(listed)
        return listed[0]

    def candidates(self, text: str) -> list[GlobalInstrument]:
        return list(self._by_ticker.get((text or "").strip().upper(), []))


class BrokerSymbolMapper:
    """Canonical instrument_id <-> broker-specific symbol. Separate component."""

    def __init__(self):
        self._map: dict[tuple[str, str], str] = {}

    def register(self, broker_id: str, instrument_id: str, symbol: str) -> None:
        self._map[(broker_id, instrument_id)] = symbol

    def to_broker(self, broker_id: str, instrument_id: str) -> str:
        try:
            return self._map[(broker_id, instrument_id)]
        except KeyError:
            raise UnknownInstrument(
                f"no {broker_id} mapping for {instrument_id} — execution blocked")


__all__ = ["GlobalInstrument", "GlobalResolver", "BrokerSymbolMapper",
           "AmbiguousInstrument", "UnknownInstrument"]
