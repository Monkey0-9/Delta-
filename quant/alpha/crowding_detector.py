"""Alpha crowding detector.

Measures crowding via pairwise return correlation (consensus) and a
flow-toxicity proxy (volume-driven reversal pressure).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass(frozen=True, slots=True)
class CrowdingDetectorParameters:
    """Parameters for CrowdingDetector."""
    corr_threshold: float = 0.7
    toxicity_window: int = 20


class CrowdingDetector:
    """Detect crowded alpha via correlation + flow toxicity.

    - fit: learns mean pairwise correlation baseline from a return panel.
    - score: per-asset crowding contributions.
    - crowding_score: aggregate [0, 1] crowding level.
    """

    def __init__(self, params: Optional[CrowdingDetectorParameters] = None) -> None:
        self._params = params or CrowdingDetectorParameters()
        self._baseline_corr: float = 0.0
        self._fitted = False

    @staticmethod
    def _mean_pairwise_corr(R: np.ndarray) -> float:
        R = np.asarray(R, dtype=float)
        if R.ndim != 2 or R.shape[1] < 2:
            return 0.0
        C = np.corrcoef(R, rowvar=False)
        C = np.nan_to_num(C, nan=0.0)
        iu = np.triu_indices(C.shape[0], k=1)
        return float(C[iu].mean()) if len(iu[0]) else 0.0

    def _toxicity(self, returns: np.ndarray, volumes: Optional[np.ndarray]) -> float:
        r = np.asarray(returns, dtype=float)
        if r.ndim == 2:
            r = r.mean(axis=1)
        w = min(self._params.toxicity_window, len(r))
        if w < 2:
            return 0.0
        recent = r[-w:]
        if volumes is not None:
            v = np.asarray(volumes, dtype=float).ravel()
            v = v[-w:] if len(v) >= w else v
            if len(v) == w and np.isfinite(v).all() and v.std() > 0:
                vw = (v - v.min()) / (v.max() - v.min() + 1e-12)
                # Toxicity: high-volume days reversing (negative autocorr proxy)
                signed = np.sign(recent) * (0.5 + 0.5 * vw)
                return float(np.clip(-np.corrcoef(signed[:-1], signed[1:])[0, 1] * 0.5 + 0.5, 0, 1))
        # Fallback: absolute trailing mean scaled by vol
        vol = recent.std() + 1e-12
        return float(np.clip(abs(recent.mean()) / vol, 0.0, 1.0))

    def fit(self, returns_panel: np.ndarray) -> "CrowdingDetector":
        """Learn baseline correlation from a (T, N) return panel."""
        self._baseline_corr = self._mean_pairwise_corr(returns_panel)
        self._fitted = True
        return self

    def score(self, returns_panel: np.ndarray) -> np.ndarray:
        """Per-asset crowding score in [0, 1].

        Combines each asset's mean correlation to peers with the
        panel toxicity proxy.
        """
        R = np.asarray(returns_panel, dtype=float)
        if R.ndim != 2 or R.shape[1] == 0:
            raise ValueError("returns_panel must be a (T, N) array.")
        C = np.corrcoef(R, rowvar=False)
        C = np.nan_to_num(C, nan=0.0)
        n = C.shape[0]
        if n < 2:
            return np.zeros(n)
        mean_corr = (C.sum(axis=1) - 1.0) / (n - 1)
        norm_corr = np.clip((mean_corr - 0.0) / 1.0, 0.0, 1.0)
        tox = self._toxicity(R, None)
        return np.clip(0.7 * norm_corr + 0.3 * tox, 0.0, 1.0)

    def crowding_score(
        self,
        returns_panel: np.ndarray,
        volumes: Optional[np.ndarray] = None,
    ) -> float:
        """Aggregate crowding level in [0, 1]."""
        R = np.asarray(returns_panel, dtype=float)
        corr = self._mean_pairwise_corr(R)
        tox = self._toxicity(R, volumes)
        return float(np.clip(0.6 * max(corr, 0.0) + 0.4 * tox, 0.0, 1.0))


__all__ = ["CrowdingDetectorParameters", "CrowdingDetector"]
