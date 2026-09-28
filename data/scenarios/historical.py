"""W151-W160 historical stress scenario replay manifests.

Actual replayable datasets (not volatility multipliers). Each manifest pins:
symbol universe, interval, source, dataset hash placeholder, and the
microstructure note (daily-bar source resampled through the L2 engine;
replace with vendor L1/L2 when a feed is configured).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


def _manifest_hash(scenario_id: str, label: str, interval: str, universe: str,
                   source: str, seed: int) -> str:
    """Content hash of the manifest itself (integrity, not data provenance).

    The full dataset hash is computed when replay files land on disk; until
    then verified=False and the scenario must not back a live decision.
    """
    raw = json.dumps({"scenario_id": scenario_id, "label": label, "interval": interval,
                      "universe": universe, "source": source, "seed": seed},
                     sort_keys=True, separators=(",", ":")).encode()
    return "manifest-sha:" + hashlib.sha256(raw).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class HistoricalScenario:
    scenario_id: str
    label: str
    interval: str  # train/validation/OOS slice for replay
    universe: str
    source: str
    dataset_hash: str
    microstructure: str = "bar-resampled-l2-NOT-vendor-ticks"
    seed: int = 7
    verified: bool = False  # True only when replay files exist and hash matches


def _make(scenario_id: str, label: str, interval: str, universe: str,
          source: str, seed: int = 7) -> HistoricalScenario:
    return HistoricalScenario(
        scenario_id=scenario_id, label=label, interval=interval,
        universe=universe, source=source,
        dataset_hash=_manifest_hash(scenario_id, label, interval, universe, source, seed),
        seed=seed, verified=False)


SCENARIOS: tuple[HistoricalScenario, ...] = (
    _make("HIST-2008-GFC", "2008 crisis replay", "2007-01-01 -> 2009-12-31",
          "SPY/QQQ/IWM/DIA", "yahoo-finance+daily-bars"),
    _make("HIST-2010-FLASH", "2010 flash-crash style event", "2010-04-01 -> 2010-06-30",
          "SPY/QQQ", "yahoo-finance+daily-bars"),
    _make("HIST-2020-COVID", "2020 COVID shock", "2019-06-01 -> 2020-12-31",
          "SPY/QQQ/IWM/VIX-proxy", "yahoo-finance+daily-bars"),
    _make("HIST-2022-RATES", "2022 rates/inflation shock", "2021-06-01 -> 2022-12-31",
          "SPY/TLT/QQQ", "yahoo-finance+fred+daily-bars"),
    _make("HIST-2018-VOL", "2018 volatility shock", "2017-10-01 -> 2018-12-31",
          "SPY/QQQ", "yahoo-finance+daily-bars"),
    _make("HIST-2015-VOL", "2015 volatility shock", "2015-01-01 -> 2015-12-31",
          "SPY/QQQ", "yahoo-finance+daily-bars"),
)


def get(scenario_id: str) -> HistoricalScenario:
    for s in SCENARIOS:
        if s.scenario_id == scenario_id:
            return s
    raise KeyError(f"unknown historical scenario: {scenario_id}.")
