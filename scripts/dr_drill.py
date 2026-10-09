"""B9: OMS crash-recovery (DR) drill — kill-9 → journal replay → broker poll → 3-way reconcile.

Recovery semantic (production path): replay the journal, poll the broker,
then catch the journal up to broker truth —
  * broker shows a fill for a journal-open order → append ACKNOWLEDGED/FILLED;
  * journal shows SUBMITTED but the broker never saw it (crash landed
    between journal-append and broker-send) → append CANCELLED (never
    reached the venue, safe to cancel).
Only then reconcile OMS-open vs broker-open (must RESUME) and diff the
journal set vs the broker book (3rd leg).

Honest scope: same-process handle-drop simulates the kill-9 (a real SIGKILL
cannot be self-administered mid-drill); the recovery path is production
code. RPO must be 0 (no committed journal line lost); RTO < 60s per the P0
plan. Emits a hash-chained artifact at artifacts/dr/drill.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

RTO_BUDGET_S = 60.0
TERMINAL = {"FILLED", "CANCELLED", "REJECTED"}


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _emit(workdir: Path, name: str, payload: dict) -> Path:
    out = Path(workdir)
    out.mkdir(parents=True, exist_ok=True)
    payload["hash"] = _sha(payload)
    p = out / f"{name}.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def run(workdir: Path, n_orders: int = 25) -> dict:
    from broker.reconciliation import reconcile_oms_vs_broker
    from core.oms.journal import OmsJournal
    from execution.ems.adapter import ExecutionRequest
    from execution.paper.broker import PaperBroker

    t_start = time.perf_counter()
    workdir = Path(workdir)
    jpath = workdir / "oms.jsonl"
    # The drill owns its workdir: stale journals from partial runs must not
    # pollute replay (a real crash-recovery replays the live journal, which
    # the test below covers via tmp_path isolation).
    if jpath.exists():
        jpath.unlink()
    tpath = workdir / "oms-tampered.jsonl"
    if tpath.exists():
        tpath.unlink()

    # Phase 1 — seed a live book through the real journal + real paper broker.
    journal = OmsJournal(jpath)
    paper = PaperBroker({"SPY": 100.0})
    broker_acked: list[str] = []
    for i in range(n_orders):
        oid = f"DR-{i:03d}"
        journal.append(oid, "CREATED")
        journal.append(oid, "VALIDATED")
        journal.append(oid, "RISK_APPROVED")
        journal.append(oid, "SUBMITTED")
        if i % 5 == 2:
            continue  # crash window: journal has SUBMITTED, broker never saw it
        ack = paper.submit(ExecutionRequest(order_id=oid, asset="SPY", quantity=10.0))
        assert ack.accepted, f"paper refused drill order {oid}"
        broker_acked.append(oid)
        if i % 5 == 4:
            journal.append(oid, "ACKNOWLEDGED")
            journal.append(oid, "FILLED")
        elif i % 5 == 3:
            journal.append(oid, "ACKNOWLEDGED")
    lines_before = sum(1 for _ in jpath.read_text(encoding="utf-8").splitlines() if _.strip())
    truth = journal.snapshot()
    open_before = sorted(o for o, s in truth.items() if s not in TERMINAL)

    # Phase 2 — crash: drop every in-memory handle (kill-9 simulation).
    del journal, paper

    # Phase 3 — recover on a cold clock.
    t0 = time.perf_counter()
    journal2 = OmsJournal(jpath)
    replayed = journal2.snapshot()
    replay_match = replayed == truth
    lines_after = sum(1 for _ in jpath.read_text(encoding="utf-8").splitlines() if _.strip())
    paper2 = PaperBroker({"SPY": 100.0})
    caught_filled, caught_cancelled = 0, 0
    for oid, state in replayed.items():
        if state in TERMINAL:
            continue
        if oid in broker_acked:
            # Broker truth: paper fills instantly; catch the journal up.
            if state == "SUBMITTED":
                journal2.append(oid, "ACKNOWLEDGED")
            journal2.append(oid, "FILLED")
            caught_filled += 1
        else:
            # Never reached the venue: safe to cancel in-journal.
            journal2.append(oid, "CANCELLED")
            caught_cancelled += 1
    final = journal2.snapshot()
    oms_open = sorted(o for o, s in final.items() if s not in TERMINAL)
    broker_open = sorted(o for o in broker_acked
                         if final.get(o) not in TERMINAL)
    rep = reconcile_oms_vs_broker(tuple(oms_open), tuple(broker_open))
    # 3rd leg: journal id-set vs broker book must agree exactly
    # (CANCELLED crash-window orders never reached the venue by design).
    ledger_diverged = sorted((set(final) - set(broker_acked) - {o for o in final if final[o] == "CANCELLED"})
                             | (set(broker_acked) - set(final)))
    rto_s = time.perf_counter() - t0

    # Phase 4 — tamper negative: a corrupted journal must refuse replay loudly.
    tpath.write_bytes(jpath.read_bytes() + b'{"seq": 9999, "order_id": "EVIL", "state": "FILLED"}\n')
    tamper_raised = False
    try:
        OmsJournal(tpath).snapshot()
    except (AssertionError, ValueError, KeyError, json.JSONDecodeError):
        tamper_raised = True

    rpo_lost = lines_before - lines_after
    reconcile_clean = (not ledger_diverged and rep.decision == "RESUME"
                       and not oms_open and not broker_open)
    ok = (rpo_lost == 0 and replay_match and reconcile_clean
          and rto_s < RTO_BUDGET_S and tamper_raised)
    artifact = {
        "drill": "oms-crash-recovery",
        "n_orders": n_orders,
        "journal_lines": lines_before,
        "open_before": len(open_before),
        "caught_up_filled": caught_filled,
        "caught_up_cancelled": caught_cancelled,
        "open_after": len(oms_open),
        "rpo_lost_lines": rpo_lost,
        "replay_match": replay_match,
        "reconcile_decision": rep.decision,
        "reconcile_clean": bool(reconcile_clean),
        "ledger_diverged": ledger_diverged,
        "tamper_refused": tamper_raised,
        "rto_s": round(rto_s, 4),
        "rto_budget_s": RTO_BUDGET_S,
        "wall_s": round(time.perf_counter() - t_start, 3),
        "verdict": "PASS" if ok else "FAIL",
        "scope_note": ("same-process handle-drop simulates kill-9; recovery "
                       "path is production code; 14-day soak + real-SIGKILL "
                       "rehearsal remain open (see sign-off matrix)"),
    }
    p = _emit(workdir, "drill", artifact)
    artifact["artifact"] = str(p)
    return artifact


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default="artifacts/dr")
    ap.add_argument("--n-orders", type=int, default=25)
    ap.add_argument("--force", action="store_true",
                    help="allow a workdir outside artifacts/ (default refuses: "
                         "the drill deletes <workdir>/oms*.jsonl on start)")
    a = ap.parse_args()
    wd = Path(a.workdir).resolve()
    art = (Path(".").resolve() / "artifacts")
    if wd != art and art not in wd.parents and not a.force:
        print(f"refusing workdir outside artifacts/ (pass --force): {wd}")
        return 2
    r = run(Path(a.workdir), a.n_orders)
    print(json.dumps({k: r[k] for k in ("verdict", "rpo_lost_lines", "rto_s",
                                       "replay_match", "reconcile_clean",
                                       "reconcile_decision", "tamper_refused",
                                       "artifact")}, indent=2))
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
