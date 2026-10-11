"""B10: benchmark certification — real measurements on THIS box, honest verdicts.

Benches (all production code paths, wall-clock timed):
  * risk firewall per-check latency distribution (TradeIntent → check);
  * OMS journal append throughput;
  * OrderGateway submit end-to-end (paper-routed, no broker send);
  * native LOB (NativeMatcher add/top) when the native bridge is available,
    else UNMEASURED with reason (never a fabricated number).
Targets come from the P0 plan (firewall <7µs/check; LOB 10M ops/s). A missed
target is FAIL/UNMEASURED in the artifact — never adjusted. Per ADR-0009 the
P0 targets are LIVE-gate aspirations for isolated hardware; the approved
PAPER/RESEARCH requirement is the measured baseline + SRE regression guard.
Machine context
(OS/CPU/Python) is recorded so numbers are reproducible-or-explained.
Emits hash-chained artifacts/bench/bench.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")

FIREWALL_TARGET_US = 7.0
LOB_TARGET_OPS = 10_000_000


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _dist(samples_us: list[float]) -> dict:
    s = sorted(samples_us)
    n = len(s)

    def pct(p: float) -> float:
        return s[min(n - 1, int(n * p))]
    return {"n": n, "p50_us": round(pct(0.50), 3), "p95_us": round(pct(0.95), 3),
            "p99_us": round(pct(0.99), 3), "p99_9_us": round(pct(0.999), 3),
            "max_us": round(s[-1], 3),
            "ops_per_s": round(n / (sum(s) / 1e6), 1) if sum(s) > 0 else 0.0}


def _stamp(d: dict) -> dict:
    d["measured_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return d


UNMEASURED_KERNELS = (
    "lob_insert", "lob_cancel", "lob_replace", "lob_match",
    "dedup", "serialization",
)


def _unavailable_kernel(name: str) -> dict:
    return _stamp({"verdict": "UNAVAILABLE",
                   "reason": (f"{name}: not yet benched in isolation on "
                              "this box — no number claimed")})


def bench_firewall(n: int = 2000) -> dict:
    from risk.firewall.firewall import RiskFirewall
    from risk.pre_trade.validation import TradeIntent
    fw = RiskFirewall()
    lat: list[float] = []
    for _ in range(n):
        intent = TradeIntent(order_id=uuid4(), instrument_id=uuid4(),
                             side="buy", quantity=Decimal("10"))
        t0 = time.perf_counter()
        fw.check(intent, ref_price=Decimal("100"))
        lat.append((time.perf_counter() - t0) * 1e6)
    d = _dist(lat)
    d["target_us"] = FIREWALL_TARGET_US
    d["verdict"] = "PASS" if d["p99_us"] <= FIREWALL_TARGET_US else "FAIL"
    return d


def bench_journal(n: int = 2000, path: Path | None = None) -> dict:
    from core.oms.journal import OmsJournal
    p = (path or Path("artifacts/bench")) / "bench-oms.jsonl"
    if p.exists():
        p.unlink()
    j = OmsJournal(p)
    lat: list[float] = []
    for i in range(n):
        oid = f"BENCH-{i:05d}"
        t0 = time.perf_counter()
        j.append(oid, "CREATED")
        j.append(oid, "VALIDATED")
        lat.append((time.perf_counter() - t0) * 1e6 / 2)
    d = _dist(lat)
    d["target_us"] = None
    d["verdict"] = "MEASURED"
    return d


def bench_gateway(n: int = 200) -> dict:
    from core.domain.order import Order, OrderSide
    from core.oms.gateway import OrderGateway
    from risk.firewall.firewall import RiskFirewall
    import warnings
    gw = OrderGateway(firewall=RiskFirewall())
    lat: list[float] = []
    approved = 0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        for _ in range(n):
            o = Order(instrument_id=uuid4(), side=OrderSide.BUY,
                      quantity=Decimal("10"))
            t0 = time.perf_counter()
            dec = gw.submit(o, ref_price=Decimal("100"), authorized=True,
                            price_source="real", actor="bench",
                            role="risk_officer")
            lat.append((time.perf_counter() - t0) * 1e6)
            approved += bool(dec.approved)
    d = _dist(lat)
    d["approved"] = approved
    d["target_us"] = None
    d["verdict"] = "MEASURED"
    return d


def bench_lob(n: int = 20000) -> dict:
    try:
        from native.lob import NativeMatcher, available
    except Exception as exc:
        return {"verdict": "UNMEASURED", "reason": f"native.lob import failed: {exc}"}
    if not available():
        return {"verdict": "UNMEASURED", "reason": "native bridge unavailable on this box"}
    m = NativeMatcher()
    t0 = time.perf_counter()
    for i in range(n):
        m.add(f"LOBB-{i}", "buy", Decimal(str(100.0 + (i % 50) * 0.01)),
              Decimal("10"))
    dt = time.perf_counter() - t0
    ops = round(n / dt, 1) if dt > 0 else 0.0
    return {"n": n, "ops_per_s": ops, "target_ops": LOB_TARGET_OPS,
            "verdict": "PASS" if ops >= LOB_TARGET_OPS else "FAIL"}


def machine() -> dict:
    try:  # optional; absence is reported as unknown, never fabricated
        import psutil  # type: ignore
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        ram_gb = "unknown"
    return {"os": platform.platform(), "cpu_count": os.cpu_count(),
            "cpu_model": platform.processor() or "unknown",
            "ram_gb": ram_gb, "python": platform.python_version(),
            "measured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def run(workdir: Path, n_firewall: int = 2000, n_journal: int = 2000,
        n_gateway: int = 200, n_lob: int = 20000) -> dict:
    t0 = time.perf_counter()
    fw = _stamp(bench_firewall(n_firewall))
    jo = _stamp(bench_journal(n_journal, Path(workdir)))
    gw = _stamp(bench_gateway(n_gateway))
    lob = _stamp(bench_lob(n_lob))
    measured = {"firewall_check": fw, "journal_append": jo, "gateway_submit": gw,
                "native_lob": lob}
    for k in UNMEASURED_KERNELS:
        measured[k] = _unavailable_kernel(k)
    blockers = [k for k, v in measured.items() if v.get("verdict") == "FAIL"]
    unmeasured = [k for k, v in measured.items()
                  if v.get("verdict") in ("UNMEASURED", "UNAVAILABLE")]
    verdict = "FAIL" if blockers else ("PARTIAL" if unmeasured else "PASS")
    artifact = {"bench": "certification", "machine": machine(),
                "components": measured, "blockers": blockers,
                "unmeasured": unmeasured, "verdict": verdict,
                "wall_s": round(time.perf_counter() - t0, 2),
                "scope_note": ("this-box numbers only; documented-hardware "
                               "p50/p95/p99/p99.9 runs remain open until measured "
                               "on isolated hardware per the P0 plan")}
    artifact["hash"] = _sha(artifact)
    out = Path(workdir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "bench.json"
    p.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    artifact["artifact"] = str(p)
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="artifacts/bench")
    ap.add_argument("--n-firewall", type=int, default=2000)
    ap.add_argument("--n-journal", type=int, default=2000)
    ap.add_argument("--n-gateway", type=int, default=200)
    ap.add_argument("--n-lob", type=int, default=20000)
    a = ap.parse_args()
    r = run(Path(a.workdir), a.n_firewall, a.n_journal, a.n_gateway, a.n_lob)
    print(json.dumps({k: r[k] for k in ("verdict", "blockers", "unmeasured",
                                       "wall_s", "artifact")}, indent=2))
    print(json.dumps({k: {kk: v[kk] for kk in ("p50_us", "p95_us", "p99_us", "p99_9_us",
                                                          "verdict", "measured_utc")
                                     if kk in v} for k, v in r["components"].items()
                      if k != "native_lob"}, indent=2))
    print(json.dumps({"native_lob": r["components"]["native_lob"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
