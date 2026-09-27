from __future__ import annotations

import re


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key)\s*[:=]\s*[^\s,]+"),
    re.compile(r"(?i)(secret)\s*[:=]\s*[^\s,]+"),
    re.compile(r"(?i)(password)\s*[:=]\s*[^\s,]+"),
    re.compile(r"(?i)(token)\s*[:=]\s*[^\s,]+"),
)


def redact_secrets(text: str) -> str:
    result = text

    for pattern in _SECRET_PATTERNS:
        result = pattern.sub(
            lambda match: f"{match.group(1)}=[REDACTED]",
            result,
        )

    return result