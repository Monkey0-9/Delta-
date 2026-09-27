"""Input validation and sanitization: length, type, charset, injection guards."""
from __future__ import annotations

import re

_MAX_LEN = 10_000
_SUSPICIOUS = (
    re.compile(r"(?i)\b(ignore|disregard)\s+(all\s+)?(prior|previous|system)\s+(instructions|prompts)"),
    re.compile(r"(?i)\b(execute|run|eval|system|popen|subprocess)\s*\("),
    re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"),
)


def sanitize_text(value: object, *, field: str = "input", max_len: int = _MAX_LEN) -> str:
    """Coerce to str, enforce length, reject control chars and injection patterns."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string.")
    if len(value) > max_len:
        raise ValueError(f"{field} exceeds max length {max_len}.")
    for pattern in _SUSPICIOUS:
        if pattern.search(value):
            raise ValueError(f"{field} rejected: suspicious content.")
    return value


def sanitize_symbol(symbol: object) -> str:
    """Exchange symbols: 1-12 chars, uppercase alnum plus . - _."""
    if not isinstance(symbol, str) or not re.fullmatch(r"[A-Z0-9.\-_]{1,12}", symbol.strip().upper()):
        raise ValueError(f"invalid symbol: {symbol!r}.")
    return symbol.strip().upper()


def sanitize_quantity(value: object, *, field: str = "quantity") -> float:
    from decimal import Decimal

    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{field} must be numeric.")
    if not (float("-inf") < float(value) < float("inf")) or float(value) <= 0:
        raise ValueError(f"{field} must be finite and positive.")
    return float(value)
