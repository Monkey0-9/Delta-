from __future__ import annotations

from decimal import Decimal
from math import sqrt
from typing import Iterable, Sequence, TypeAlias

Number: TypeAlias = int | float | Decimal


def _values(values: Sequence[Number] | Iterable[Number]) -> list[Number]:
    data = list(values)

    if not data:
        raise ValueError("Values cannot be empty.")

    return data


def _is_decimal_sequence(values: Sequence[Number]) -> bool:
    return any(isinstance(value, Decimal) for value in values)


def _zero_like(values: Sequence[Number]) -> Number:
    if _is_decimal_sequence(values):
        return Decimal("0")
    return 0.0


def _one_like(values: Sequence[Number]) -> Number:
    if _is_decimal_sequence(values):
        return Decimal("1")
    return 1.0


def arithmetic_returns(
    prices: Sequence[Number] | Iterable[Number],
) -> tuple[Number, ...]:
    """
    Calculate simple arithmetic returns.

    For prices P[t]:

        r[t] = P[t] / P[t-1] - 1

    The first observation is omitted.

    Decimal inputs remain Decimal to preserve exact financial arithmetic.
    """

    data = _values(prices)

    if len(data) < 2:
        return ()

    returns: list[Number] = []

    for previous, current in zip(data, data[1:]):
        if previous == 0:
            raise ValueError("Previous price cannot be zero.")

        # Decimal arithmetic stays Decimal.
        if isinstance(previous, Decimal) or isinstance(current, Decimal):
            previous_d = (
                previous
                if isinstance(previous, Decimal)
                else Decimal(str(previous))
            )
            current_d = (
                current
                if isinstance(current, Decimal)
                else Decimal(str(current))
            )

            returns.append(current_d / previous_d - Decimal("1"))
        else:
            returns.append(current / previous - 1)  # type: ignore[operator]

    return tuple(returns)


def simple_returns(
    prices: Sequence[Number] | Iterable[Number],
) -> tuple[Number, ...]:
    """Alias for arithmetic_returns."""
    return arithmetic_returns(prices)


def mean_return(
    returns: Sequence[Number] | Iterable[Number],
) -> Number:
    """
    Arithmetic mean of returns.

    Preserves Decimal arithmetic when Decimal values are supplied.
    """

    data = _values(returns)

    if _is_decimal_sequence(data):
        total = sum(
            (
                value
                if isinstance(value, Decimal)
                else Decimal(str(value))
            )
            for value in data
        )
        return total / Decimal(len(data))

    return sum(data) / len(data)  # type: ignore[operator]


def variance(
    values: Sequence[Number] | Iterable[Number],
    *,
    sample: bool = True,
) -> Number:
    """
    Calculate variance.

    sample=True:
        sample variance using n - 1.

    sample=False:
        population variance using n.

    A single observation has zero variance.
    """

    data = _values(values)

    if len(data) == 1:
        return _zero_like(data)

    mean = mean_return(data)

    if _is_decimal_sequence(data):
        mean_d = (
            mean
            if isinstance(mean, Decimal)
            else Decimal(str(mean))
        )

        squared = [
            (
                value
                if isinstance(value, Decimal)
                else Decimal(str(value))
            )
            - mean_d
            for value in data
        ]

        total = sum((difference * difference for difference in squared), Decimal("0"))

        denominator = len(data) - 1 if sample else len(data)

        return total / Decimal(denominator)

    total_float = sum(
        (float(value) - float(mean)) ** 2
        for value in data
    )

    denominator = len(data) - 1 if sample else len(data)

    return total_float / denominator


def volatility(
    returns: Sequence[Number] | Iterable[Number],
    *,
    sample: bool = True,
) -> Number:
    """Standard deviation of returns."""

    value = variance(returns, sample=sample)

    if isinstance(value, Decimal):
        return value.sqrt()

    return sqrt(value)


def annualized_volatility(
    returns: Sequence[Number] | Iterable[Number],
    *,
    periods_per_year: int = 252,
    sample: bool = True,
) -> Number:
    """Annualized volatility."""

    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive.")

    vol = volatility(returns, sample=sample)

    if isinstance(vol, Decimal):
        return vol * Decimal(periods_per_year).sqrt()

    return vol * sqrt(periods_per_year)


def cumulative_return(
    returns: Sequence[Number] | Iterable[Number],
) -> Number:
    """
    Compound a sequence of arithmetic returns.
    """

    data = _values(returns)

    if _is_decimal_sequence(data):
        result = Decimal("1")

        for value in data:
            value_d = (
                value
                if isinstance(value, Decimal)
                else Decimal(str(value))
            )
            result *= Decimal("1") + value_d

        return result - Decimal("1")

    result = 1.0

    for value in data:
        result *= 1.0 + float(value)

    return result - 1.0


def downside_deviation(
    returns: Sequence[Number] | Iterable[Number],
    *,
    target: Number = 0,
) -> Number:
    """Downside deviation relative to target."""

    data = _values(returns)

    if _is_decimal_sequence(data) or isinstance(target, Decimal):
        target_d = (
            target
            if isinstance(target, Decimal)
            else Decimal(str(target))
        )

        negatives = []

        for value in data:
            value_d = (
                value
                if isinstance(value, Decimal)
                else Decimal(str(value))
            )

            if value_d < target_d:
                difference = value_d - target_d
                negatives.append(difference * difference)

        if not negatives:
            return Decimal("0")

        return (
            sum(negatives, Decimal("0")) / Decimal(len(data))
        ).sqrt()

    squared = [
        (float(value) - float(target)) ** 2
        for value in data
        if float(value) < float(target)
    ]

    if not squared:
        return 0.0

    return sqrt(sum(squared) / len(data))


def max_drawdown(
    values: Sequence[Number] | Iterable[Number],
) -> Number:
    """
    Maximum drawdown from a running peak.

    Example:

        [100, 120, 90, 110]

    Maximum drawdown = 25%.
    """

    data = _values(values)

    if _is_decimal_sequence(data):
        peak = (
            data[0]
            if isinstance(data[0], Decimal)
            else Decimal(str(data[0]))
        )

        maximum = Decimal("0")

        for value in data:
            current = (
                value
                if isinstance(value, Decimal)
                else Decimal(str(value))
            )

            if current > peak:
                peak = current

            if peak == 0:
                raise ValueError("Peak value cannot be zero.")

            drawdown = (peak - current) / peak

            if drawdown > maximum:
                maximum = drawdown

        return maximum

    peak = float(data[0])
    maximum = 0.0

    for value in data:
        current = float(value)

        if current > peak:
            peak = current

        if peak == 0:
            raise ValueError("Peak value cannot be zero.")

        drawdown = (peak - current) / peak

        if drawdown > maximum:
            maximum = drawdown

    return maximum


__all__ = [
    "arithmetic_returns",
    "simple_returns",
    "variance",
    "mean_return",
    "volatility",
    "annualized_volatility",
    "cumulative_return",
    "downside_deviation",
    "max_drawdown",
]