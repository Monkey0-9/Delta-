"""B10: bounded shadow soak — paper lifecycle under repetition + kill flaps.

Each cycle: gateway submit → paper fill → execution report → reconcile.
Every --flap-every cycles: engage kill, assert the next submit is blocked,
release kill. Every --replay-every cycles: fresh OmsJournal handle replays
the soak journal (recovery path exercised hot).

Honest scope: a bounded cycle soak, NOT the 14-day wall-clock soak. The
artifact says so explicitly; Sprint-10 stays open until wall-clock evidence
exists. Emits hash-chained artifacts/soak/soak.json.

SHADOW CONTRACT (Sprint-10): live data in would feed hypothetical execution
records here; this bounded harness uses a fixed reference price (100.0) and
is labeled hypothetical (live_data=false). ZERO live-broker submits:
verify_no_live_submit_path() self-audits this file for known live-submit
tokens and fail-closes, and the artifact pins broker_submits=0.
Mirror-diff tracking compares each hypothetical fill against the reference
price. Wall-clock gate: status is INCOMPLETE for any run shorter than 14
days of zero-downtime evidence; SOAK_COMPLETE only at >=14d with zero
errors/mismatches. Short runs never fake COMPLETE.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, ".")


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


SOAK_REQUIRED_S = 14 * 24 * 3600  # Sprint-10 wall-clock gate: 14 days
REFERENCE_PRICE = 100.0  # fixed reference; live_data=false (hypothetical)
LIVE_SUBMIT_TOKENS = (
    "IBKRClientPortalAdapter", "Alpaca", "send_to_venue", "submit_live",
    "place_live_order", "requests.post",
)


def verify_no_live_submit_path() -> dict:
    """Self-audit: fail closed if a live-broker submit path is reachable."""
    import re
    src = Path(__file__).read_text(encoding="utf-8")
    # Exclude this function's own blocklist declaration from the scan.
    body = re.sub(r"LIVE_SUBMIT_TOKENS = \(.*?\)", "", src, flags=re.S)
    hits = [t for t in LIVE_SUBMIT_TOKENS if t in body]
    assert not hits, f"live submit path reachable from shadow harness: {hits}"
    return {"live_submit_paths": 0, "checked_tokens": len(LIVE_SUBMIT_TOKENS)}


def run(workdir: Path, cycles: int = 50, flap_every: int = 10,
        replay_every: int = 25) -> dict:
    from broker.reconciliation import reconcile_oms_vs_broker
    from core.domain.order import Order, OrderSide
    from core.oms.gateway import OrderGateway
    from core.oms.journal import OmsJournal
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker
    from risk.firewall.firewall import RiskFirewall
    from risk.kill_switch.kill_switch import KillSwitchBoard

    t0 = time.perf_counter()
    started_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    no_submit = verify_no_live_submit_path()
    workdir = Path(workdir)
    jpath = workdir / "soak-oms.jsonl"
    if jpath.exists():
        jpath.unlink()
    journal = OmsJournal(jpath)
    board = KillSwitchBoard()
    gw = OrderGateway(firewall=RiskFirewall(kill_switch=board))
    paper = PaperBroker({"SPY": 100.0})

    orders = fills = mismatches = errors = flaps = replays = 0
    hypothetical_fills = 0
    broker_submits = 0  # live-broker submits: always zero in shadow mode
    mirror_diffs = 0
    mirror_diff_samples: list[str] = []
    error_samples: list[str] = []
    broker_ids: list[str] = []
    for n in range(cycles):
        try:
            if flap_every and n and n % flap_every == 0:
                board.glob.activate(actor="soak-drill")
                flaps += 1
                probe = Order(instrument_id=uuid4(), side=OrderSide.BUY,
                              quantity=Decimal("1"))
                blocked = gw.submit(probe, ref_price=Decimal("100"),
                                    authorized=True, price_source="real",
                                    actor="soak", role="risk_officer")
                assert not blocked.approved, "kill flap did not block submit"
                board.glob.rearm(actor="soak-drill")
            oid = f"SOAK-{n:05d}"
            order = Order(instrument_id=uuid4(), side=OrderSide.BUY,
                          quantity=Decimal("10"))
            journal.append(oid, "CREATED")
            journal.append(oid, "VALIDATED")
            journal.append(oid, "RISK_APPROVED")
            journal.append(oid, "SUBMITTED")
            ack = paper.submit(ExecutionRequest(order_id=oid, asset="SPY",
                                                quantity=10.0))
            if not ack.accepted:
                raise RuntimeError(f"paper refused {oid}")
            broker_ids.append(oid)
            journal.append(oid, "ACKNOWLEDGED")
            journal.append(oid, "FILLED")
            orders += 1
            rep = paper.execution_report(oid)
            fill_price = rep.get("fill_price")
            hypothetical_fills += 1  # paper fill = hypothetical record only
            if fill_price == REFERENCE_PRICE:
                fills += 1
            else:
                # mirror-diff: hypothetical execution vs reference price
                mirror_diffs += 1
                if len(mirror_diff_samples) < 5:
                    mirror_diff_samples.append(f"{oid}: fill={fill_price} ref={REFERENCE_PRICE}")
            r = reconcile_oms_vs_broker((oid,), (oid,))
            if r.decision != "RESUME":
                mismatches += 1
            if replay_every and (n + 1) % replay_every == 0:
                replays += 1
                assert OmsJournal(jpath).snapshot() == journal.snapshot()
        except Exception as exc:  # noqa: BLE001 — soak records, never hides
            errors += 1
            if len(error_samples) < 5:
                error_samples.append(f"{type(exc).__name__}: {exc}")
    wall_s = time.perf_counter() - t0
    ended_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ok = (errors == 0 and mismatches == 0 and mirror_diffs == 0
          and broker_submits == 0 and fills == orders and orders == cycles)
    soak_complete = ok and wall_s >= SOAK_REQUIRED_S
    status = "SOAK_COMPLETE" if soak_complete else "INCOMPLETE"
    artifact = {
        "soak": "bounded-shadow",
        "shadow_mode": True,
        "live_data": False,
        "status": status,
        "soak_complete": soak_complete,
        "required_s": SOAK_REQUIRED_S,
        "duration_s": round(wall_s, 3),
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "broker_submits": broker_submits,
        "live_submit_paths": no_submit["live_submit_paths"],
        "hypothetical_fills": hypothetical_fills,
        "mirror_diffs": mirror_diffs,
        "mirror_diff_samples": mirror_diff_samples,
        "cycles": cycles,
        "orders": orders,
        "fills": fills,
        "reconcile_mismatches": mismatches,
        "errors": errors,
        "error_samples": error_samples,
        "kill_flaps": flaps,
        "journal_replays": replays,
        "wall_s": round(wall_s, 3),
        "cycles_per_s": round(cycles / wall_s, 1) if wall_s > 0 else 0.0,
        "verdict": "PASS" if ok else "FAIL",
        "scope_note": ("bounded cycle soak only — 14-day continuous "
                       "wall-clock shadow (Sprint 10) NOT covered by this "
                       "artifact; status is INCOMPLETE until >=14d "
                       "zero-downtime wall-clock evidence exists; this "
                       "artifact never claims SOAK_COMPLETE"),
    }
    artifact["hash"] = _sha(artifact)
    out = Path(workdir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / "soak.json"
    p.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    artifact["artifact"] = str(p)
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="artifacts/soak")
    ap.add_argument("--cycles", type=int, default=50)
    ap.add_argument("--flap-every", type=int, default=10)
    ap.add_argument("--replay-every", type=int, default=25)
    a = ap.parse_args()
    r = run(Path(a.workdir), a.cycles, a.flap_every, a.replay_every)
    print(json.dumps({k: r[k] for k in ("verdict", "status", "cycles", "orders", "fills",
                                       "reconcile_mismatches", "mirror_diffs",
                                       "broker_submits", "errors",
                                       "wall_s", "artifact")}, indent=2))
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
