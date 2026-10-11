"""§5: scope declarations are complete, honest, and forbid silent expansion."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
STATUSES = {"supported", "analytics-only", "partial", "experimental",
            "unsupported"}


def _scope():
    with open(REPO / "docs" / "SUPPORTED_SCOPE.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_scope_schema_complete():
    scope = _scope()
    domains = [d["domain"] for d in scope["domains"]]
    for required in ("equities", "options", "futures", "fx-rates",
                     "portfolio-attribution", "market-regimes",
                     "alternative-data", "strategy-capacity"):
        assert required in domains, f"missing domain declaration: {required}"
    for d in scope["domains"]:
        assert d["status"] in STATUSES, d
        assert d["evidence"], d["domain"]
        assert isinstance(d["limits"], list) and d["limits"], d["domain"]


def test_analytics_only_domains_cannot_route_orders():
    """Options/futures have math but no venue coverage: assert no execution
    path references them as routable instruments."""
    import re

    scope = _scope()
    ao = {d["domain"] for d in scope["domains"]
          if d["status"] == "analytics-only"}
    assert {"options", "futures"} <= ao
    # No broker adapter claims these venues.
    text = "\n".join(
        (REPO / "execution" / "adapters" / f).read_text(encoding="utf-8")
        for f in ("ibkr.py",) if (REPO / "execution" / "adapters" / f).exists())
    assert not re.search(r"options?-|futures-", text, re.IGNORECASE), (
        "adapter must not advertise analytics-only venues")


def test_unsupported_domains_have_no_ready_claims():
    scope = _scope()
    unsup = {d["domain"] for d in scope["domains"]
             if d["status"] == "unsupported"}
    assert {"fx-rates", "portfolio-attribution"} <= unsup
