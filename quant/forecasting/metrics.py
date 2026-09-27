from __future__ import annotations

from decimal import Decimal


def log_loss(probs: tuple[Decimal, ...], outcomes: tuple[int, ...], eps: float = 1e-12) -> Decimal:
    """Binary log-loss. Fail-closed on misalignment."""
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("need non-empty aligned inputs.")
    import math

    s = 0.0
    for p, o in zip(probs, outcomes):
        pc = min(max(float(p), eps), 1.0 - eps)
        s += -(o * math.log(pc) + (1 - o) * math.log(1 - pc))
    return Decimal(str(s / len(probs)))


def reliability_bins(
    probs: tuple[Decimal, ...], outcomes: tuple[int, ...], bins: int = 10
) -> tuple[tuple[Decimal, Decimal, int], ...]:
    """Per-bin (confidence, accuracy, count) for reliability diagrams."""
    if len(probs) != len(outcomes) or not probs:
        raise ValueError("need non-empty aligned inputs.")
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in zip(probs, outcomes):
        buckets[min(int(float(p) * bins), bins - 1)].append((float(p), o))
    out: list[tuple[Decimal, Decimal, int]] = []
    for b in buckets:
        if b:
            out.append(
                (
                    Decimal(str(sum(p for p, _ in b) / len(b))),
                    Decimal(str(sum(o for _, o in b) / len(b))),
                    len(b),
                )
            )
        else:
            out.append((Decimal("0"), Decimal("0"), 0))
    return tuple(out)


class IsotonicRecalibrator:
    """Pool-adjacent-violators isotonic fit on (prob, outcome) pairs."""

    def __init__(self) -> None:
        self._xs: tuple[float, ...] = ()
        self._ys: tuple[float, ...] = ()

    def fit(
        self, probs: tuple[Decimal, ...], outcomes: tuple[int, ...]
    ) -> IsotonicRecalibrator:
        if len(probs) != len(outcomes) or not probs:
            raise ValueError("need non-empty aligned inputs.")
        pairs = sorted(zip([float(p) for p in probs], outcomes))
        blocks: list[list[float]] = [[float(o)] for _, o in pairs]
        xs: list[float] = [float(p) for p, _ in pairs]
        # PAVA on block means with x tracked at block starts
        bx = xs[:]
        i = 0
        means = [b[0] for b in blocks]
        while i < len(means) - 1:
            if means[i] <= means[i + 1]:
                i += 1
            else:
                blocks[i] = blocks[i] + blocks[i + 1]
                del blocks[i + 1]
                del bx[i + 1]
                means = [sum(b) / len(b) for b in blocks]
                i = max(i - 1, 0)
        self._xs = tuple(bx)
        self._ys = tuple(sum(b) / len(b) for b in blocks)
        return self

    def predict(self, prob: Decimal) -> Decimal:
        if not self._xs:
            raise ValueError("recalibrator not fitted.")
        p = float(prob)
        best = self._ys[0]
        for x, y in zip(self._xs, self._ys):
            if p >= x:
                best = y
            else:
                break
        return Decimal(str(best))


class PlattRecalibrator:
    """Sigmoid (Platt) scaling a + b*logit(p) fit by grid search on log-loss."""

    def __init__(self) -> None:
        self._a = 0.0
        self._b = 1.0

    def fit(
        self, probs: tuple[Decimal, ...], outcomes: tuple[int, ...]
    ) -> PlattRecalibrator:
        import math

        if len(probs) != len(outcomes) or not probs:
            raise ValueError("need non-empty aligned inputs.")
        ps = [min(max(float(p), 1e-6), 1 - 1e-6) for p in probs]
        logits = [math.log(p / (1 - p)) for p in ps]
        best, ba, bb = float("inf"), 0.0, 1.0
        for a in (-1.0, -0.5, 0.0, 0.5, 1.0):
            for b in (0.25, 0.5, 1.0, 2.0):
                s = 0.0
                for l, o in zip(logits, outcomes):
                    q = 1.0 / (1.0 + math.exp(-(a + b * l)))
                    q = min(max(q, 1e-12), 1 - 1e-12)
                    s += -(o * math.log(q) + (1 - o) * math.log(1 - q))
                if s < best:
                    best, ba, bb = s, a, b
        self._a, self._b = ba, bb
        return self

    def predict(self, prob: Decimal) -> Decimal:
        import math

        p = min(max(float(prob), 1e-6), 1 - 1e-6)
        l = math.log(p / (1 - p))
        return Decimal(str(1.0 / (1.0 + math.exp(-(self._a + self._b * l)))))
