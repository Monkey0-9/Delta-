"""Deep sequence models (PyTorch, CPU): LSTM + Transformer regressors.

Small reference architectures with fixed seeds and single-threaded CPU
execution for reproducibility. GPU acceleration applies only to large
batch training via benchmark/gpu_workloads.py — never to single-event paths.
"""
from __future__ import annotations

import numpy as np


def _windows(series: np.ndarray, lookback: int, mu: float, sd: float):
    """Build windows from PRE-FIT scaler stats (mu/sd from train only).

    Callers must fit mu/sd on the training segment and reuse them for
    validation/test. Whole-series normalization before splitting is
    look-ahead contamination and is forbidden here by construction:
    this function takes caller-supplied stats and never computes them.
    """
    import torch

    s = np.asarray(series, dtype=np.float64)
    if s.ndim != 1 or len(s) <= lookback or lookback < 2:
        raise ValueError("need 1D series longer than lookback >= 2.")
    if sd == 0:
        raise ValueError("constant series carries no signal.")
    z = (s - mu) / sd
    X = np.stack([z[i : i + lookback] for i in range(len(z) - lookback)])
    y = z[lookback:]
    return torch.tensor(X, dtype=torch.float32), torch.tensor(y, dtype=torch.float32)


def _fit_stats(train: np.ndarray) -> tuple[float, float]:
    s = np.asarray(train, dtype=np.float64)
    if s.ndim != 1 or len(s) == 0:
        raise ValueError("need non-empty 1D train segment.")
    mu, sd = float(s.mean()), float(s.std())
    if sd == 0:
        raise ValueError("constant train segment carries no signal.")
    return mu, sd


def train_val_split(series: np.ndarray, val_frac: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """Chronological split: first (1-val_frac) train, remainder validation."""
    s = np.asarray(series, dtype=np.float64)
    if s.ndim != 1:
        raise ValueError("need 1D series.")
    if not 0.0 < val_frac < 0.5:
        raise ValueError("val_frac must be in (0, 0.5).")
    cut = int(len(s) * (1.0 - val_frac))
    return s[:cut], s[cut:]


def _seeded(seed: int = 0) -> None:
    import torch

    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class LSTMForecaster:
    name = "lstm"

    def __init__(self, lookback: int = 20, hidden: int = 16, epochs: int = 5, lr: float = 0.01) -> None:
        _seeded()
        import torch.nn as nn

        self._lookback = lookback
        self._epochs = epochs
        self._lstm = nn.LSTM(input_size=1, hidden_size=hidden, batch_first=True)
        self._head = nn.Linear(hidden, 1)
        self._opt_cls = __import__("torch").optim.Adam
        self._lr = lr
        self._fitted = False
        self._mu = 0.0
        self._sd = 1.0

    def fit(self, series: np.ndarray, val_frac: float = 0.2) -> LSTMForecaster:
        import torch.nn as nn

        # Scaler fit on TRAIN segment only — never whole-series stats.
        train, _ = train_val_split(series, val_frac)
        self._mu, self._sd = _fit_stats(train)
        X, y = _windows(train, self._lookback, self._mu, self._sd)
        opt = self._opt_cls(list(self._lstm.parameters()) + list(self._head.parameters()), lr=self._lr)
        loss_fn = nn.MSELoss()
        self._lstm.train()
        for _ in range(self._epochs):
            opt.zero_grad()
            out, _ = self._lstm(X.unsqueeze(-1))
            loss = loss_fn(self._head(out[:, -1, :]).squeeze(-1), y)
            loss.backward()
            opt.step()
        self._fitted = True
        return self

    def predict_next(self, recent: np.ndarray) -> float:
        import torch

        if not self._fitted:
            raise ValueError("model not fitted.")
        r = np.asarray(recent, dtype=np.float64)
        if len(r) < self._lookback:
            raise ValueError("recent shorter than lookback.")
        z = (r[-self._lookback :] - self._mu) / self._sd
        self._lstm.eval()
        with torch.no_grad():
            out, _ = self._lstm(torch.tensor(z, dtype=torch.float32).reshape(1, -1, 1))
            return float(self._head(out[:, -1, :]).item()) * self._sd + self._mu


class TransformerForecaster:
    name = "transformer"

    def __init__(self, lookback: int = 20, d_model: int = 16, nhead: int = 2,
                 layers: int = 1, epochs: int = 5, lr: float = 0.005) -> None:
        _seeded()
        import torch.nn as nn

        if d_model % nhead != 0:
            raise ValueError("d_model must be divisible by nhead.")
        layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead, batch_first=True)
        self._enc = nn.TransformerEncoder(layer, num_layers=layers)
        self._in = nn.Linear(1, d_model)
        self._head = nn.Linear(d_model, 1)
        self._lookback = lookback
        self._epochs = epochs
        self._lr = lr
        self._fitted = False
        self._mu = 0.0
        self._sd = 1.0

    def fit(self, series: np.ndarray, val_frac: float = 0.2) -> TransformerForecaster:
        import torch
        import torch.nn as nn

        # Scaler fit on TRAIN segment only — never whole-series stats.
        train, _ = train_val_split(series, val_frac)
        self._mu, self._sd = _fit_stats(train)
        X, y = _windows(train, self._lookback, self._mu, self._sd)
        params = list(self._enc.parameters()) + list(self._in.parameters()) + list(self._head.parameters())
        opt = torch.optim.Adam(params, lr=self._lr)
        loss_fn = nn.MSELoss()
        self._enc.train()
        for _ in range(self._epochs):
            opt.zero_grad()
            h = self._enc(self._in(X.unsqueeze(-1)))
            loss = loss_fn(self._head(h[:, -1, :]).squeeze(-1), y)
            loss.backward()
            opt.step()
        self._fitted = True
        return self

    def predict_next(self, recent: np.ndarray) -> float:
        import torch

        if not self._fitted:
            raise ValueError("model not fitted.")
        r = np.asarray(recent, dtype=np.float64)
        if len(r) < self._lookback:
            raise ValueError("recent shorter than lookback.")
        z = (r[-self._lookback :] - self._mu) / self._sd
        self._enc.eval()
        with torch.no_grad():
            h = self._enc(self._in(torch.tensor(z, dtype=torch.float32).reshape(1, -1, 1)))
            return float(self._head(h[:, -1, :]).item()) * self._sd + self._mu
