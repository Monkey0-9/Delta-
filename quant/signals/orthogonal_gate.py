"""Step 1.2 bridge: SVD orthogonalization gate for alpha signal generation.

Every candidate alpha vector must pass through :func:`orthogonalize_alpha`
before reaching the portfolio layer. The gate projects ``alpha`` onto the
orthogonal complement of the existing factor basis (market return, sector
dummies, active signals) via the verified kernel
``delta_omega.alpha_risk.svd_orthogonalize`` (SVD, not QR, so rank-deficient
or collinear factor blocks cannot silently collapse the projection).

Rejection rule: residual-variance ratio < 0.25 -> ValueError + warning log::

    logger.warning(f"Alpha {alpha_name} rejected: collinear with existing "
                   f"factor basis (residual variance < 0.25)")
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)

MIN_RESIDUAL_RATIO = 0.25


def build_factor_basis(*vectors: np.ndarray) -> np.ndarray:
    """Stack 1-D factor vectors (market, sectors, active alphas) into a Q matrix.

    Returns an (n, k) matrix, or an empty array when no basis is supplied
    (gate then normalizes and passes the alpha through).
    """
    cols: list[np.ndarray] = []
    for v in vectors:
        a = np.asarray(v, float).reshape(-1)
        if a.size == 0:
            continue
        cols.append(a)
    if not cols:
        return np.empty((0, 0))
    n = cols[0].size
    for c in cols:
        if c.size != n:
            raise ValueError("factor basis vectors must share one length (fail-closed)")
    return np.column_stack(cols)


def orthogonalize_alpha(
    alpha_new: np.ndarray,
    factor_basis: np.ndarray,
    alpha_name: str = "alpha",
    min_ratio: float = MIN_RESIDUAL_RATIO,
) -> np.ndarray:
    """Project ``alpha_new`` onto complement of ``factor_basis`` via the kernel.

    Returns the unit-norm orthogonalized alpha. Raises ValueError (and logs a
    warning) when the residual ratio < ``min_ratio`` — the signal is a
    disguised variant of the existing basis and must not reach sizing.
    """
    from delta_omega.alpha_risk import svd_orthogonalize

    try:
        return svd_orthogonalize(alpha_new, factor_basis, min_ratio)
    except ValueError as exc:
        logger.warning(
            f"Alpha {alpha_name} rejected: collinear with existing "
            f"factor basis (residual variance < {min_ratio})"
        )
        raise
