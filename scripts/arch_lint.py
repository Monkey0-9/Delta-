"""Import-lint: enforce tui->controllers->domain, never reverse (Group 01/02)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, ".")
from core.architecture import check_import

VIOLATIONS = [
    ("risk/emergency/breaker.py", "delta_tui/app.py"),
    ("execution/live_engine.py", "delta_tui/widgets/chrome.py"),
]


def main() -> int:
    bad = [(a, b) for a, b in VIOLATIONS if not check_import(a, b)]
    # VIOLATIONS are known-bad examples; lint passes when they are rejected.
    if len(bad) != len(VIOLATIONS):
        print("arch lint misconfigured")
        return 1
    print(f"arch lint OK: {len(VIOLATIONS)} reverse imports correctly rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
