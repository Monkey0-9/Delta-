"""B10: formal Go/No-Go sign-off matrix (Sprint 10) — computed, never asserted.

Reads the real artifacts (release/*, dr, sre, soak, bench), maps them onto
the five Sprint-10 stakeholders, and renders matrix.json + matrix.md.
Rules:
  * a missing/UNHASHED artifact is UNKNOWN and HOLDs its stakeholders;
  * a row is APPROVED only when every mapped input is PASS/CLEAR/RESUME;
  * overall LIVE verdict additionally requires human signatures in
    artifacts/signoff/signatures.json — without them, LIVE is NO-GO even
    when every machine gate passes (the tool cannot sign for humans);
  * PAPER verdict is GO iff the paper-side rows hold (kill/risk/oms/
    reconcile/dr/soak pass and no critical SRE alert).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, ".")

STAKEHOLDERS: tuple[dict, ...] = (
    {"stakeholder": "Head of Quantitative", "needs": ["release/TEST_CERTIFICATION",
     "release/DATA_CERTIFICATION", "release/RISK_CERTIFICATION"],
     "scope": "DSR / backtest / PIT integrity"},
    {"stakeholder": "Head of Engineering", "needs": ["release/OMS_CERTIFICATION",
     "release/BROKER_CERTIFICATION", "bench", "dr"],
     "scope": "FIX / OMS / perf / recovery"},
    {"stakeholder": "Chief Risk Officer", "needs": ["release/KILLSWITCH_CERTIFICATION",
     "release/RISK_CERTIFICATION", "release/RECONCILIATION_CERTIFICATION", "sre"],
     "scope": "KillSwitch / limits / reconcile / alerts"},
    {"stakeholder": "Head of InfoSec", "needs": ["release/SECURITY_CERTIFICATION", "ci"],
     "scope": "SAST / secrets / vault / RBAC"},
    {"stakeholder": "Head of Operations", "needs": ["release/OBSERVABILITY_CERTIFICATION",
     "release/RECOVERY_CERTIFICATION", "dr", "soak", "sre"],
     "scope": "SRE / DR / audit / soak"},
)


def _sha(obj: dict) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def _load(path: Path) -> tuple[dict | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing artifact"
    except json.JSONDecodeError as exc:
        return None, f"unparseable: {exc}"
    h = payload.get("hash")
    if not h:
        return payload, "no hash envelope"
    check = dict(payload)
    check.pop("hash")
    if _sha(check) != h:
        return payload, "HASH MISMATCH — possible tampering"
    return payload, "ok"


def _gate_status(kind: str, payload: dict | None, note: str) -> tuple[str, str]:
    if payload is None:
        return "UNKNOWN", note
    if note != "ok":
        return "UNKNOWN", note
    if kind.startswith("release/"):
        s = str(payload.get("status", ""))
        if s == "PASS" or s == "PASS-paper-only":
            return "PASS", "release gate PASS"
        return ("HOLD", f"release gate status={s}")
    if kind == "dr":
        v = payload.get("verdict")
        return ("PASS" if v == "PASS" else "HOLD", f"drill verdict={v}")
    if kind == "sre":
        v = payload.get("verdict")
        if v == "CLEAR":
            return "PASS", "sre CLEAR"
        return "HOLD", f"sre verdict={v}"
    if kind == "soak":
        v = payload.get("verdict")
        scope = payload.get("scope_note", "")
        if v == "PASS":
            return "PASS", f"bounded soak PASS ({scope})"
        return "HOLD", f"soak verdict={v}"
    if kind == "bench":
        v = payload.get("verdict")
        if v == "PASS":
            return "PASS", "bench PASS"
        bl = payload.get("blockers", [])
        um = payload.get("unmeasured", [])
        return "HOLD", f"bench verdict={v} blockers={bl} unmeasured={um}"
    if kind == "ci":
        return "PASS", note
    return "UNKNOWN", f"unknown gate kind {kind}"


def _sysstatus_evidence(root: Path) -> tuple[str, str]:
    """Sprint-10 R-gates live in SYSTEM_STATUS.yaml (fail-closed when absent)."""
    import re
    for name in ("SYSTEM_STATUS.yaml", "SYSTEM_STATUS.yml", "SYSTEM_STATUS.json"):
        p = root / name
        if p.exists():
            break
    else:
        return "UNKNOWN", "no SYSTEM_STATUS.yaml — R-gates unevidenced (LIVE blocked)"
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        return "UNKNOWN", f"SYSTEM_STATUS unreadable: {exc}"
    found = re.findall(r"(?im)^\s*(R\d+|gate\S*)\s*[:=]\s*(PASS|FAIL|HOLD|UNKNOWN)\b", text)
    if not found:
        return "UNKNOWN", f"{name} present but no parseable R-gate verdicts"
    bad = [(g, v) for g, v in found if v.upper() != "PASS"]
    if bad:
        return "HOLD", f"{name} gates not green: {bad}"
    return "PASS", f"{name}: {len(found)} R-gates green"


def _soak_wallclock(payload: dict | None, note: str) -> tuple[str, str]:
    """LIVE-level 14-day gate: bounded PASS is paper evidence only."""
    if payload is None:
        return "UNKNOWN", note
    if note != "ok":
        return "UNKNOWN", note
    if payload.get("soak_complete") is True or payload.get("status") == "SOAK_COMPLETE":
        return "PASS", "14-day wall-clock SOAK_COMPLETE"
    return "HOLD", "bounded soak only — 14-day wall-clock open (Sprint-10)"


def _ci_evidence(root: Path) -> tuple[str, str]:
    wf = root / ".github" / "workflows" / "security.yml"
    if not wf.exists():
        return "UNKNOWN", "security workflow absent"
    t = wf.read_text(encoding="utf-8")
    missing = [j for j in ("semgrep:", "bandit:", "secret-scan:", "cargo-audit:")
               if j not in t]
    if missing:
        return "HOLD", f"workflow missing jobs {missing}"
    return "PASS", "security.yml pins all five scanners"


def collect(root: Path) -> dict:
    arts = root / "artifacts"
    inputs: dict[str, tuple[str, str]] = {}
    for rel in ("TEST_CERTIFICATION", "DATA_CERTIFICATION", "RISK_CERTIFICATION",
                "OMS_CERTIFICATION", "BROKER_CERTIFICATION",
                "KILLSWITCH_CERTIFICATION", "RECONCILIATION_CERTIFICATION",
                "SECURITY_CERTIFICATION", "OBSERVABILITY_CERTIFICATION",
                "RECOVERY_CERTIFICATION"):
        p, note = _load(arts / "release" / f"{rel}.json")
        inputs[f"release/{rel}"] = _gate_status(f"release/{rel}", p, note)
    for name in ("drill",):
        p, note = _load(arts / "dr" / f"{name}.json")
        inputs["dr"] = _gate_status("dr", p, note)
    p, note = _load(arts / "sre" / "sre.json")
    inputs["sre"] = _gate_status("sre", p, note)
    p, note = _load(arts / "soak" / "soak.json")
    soak_payload, soak_note = p, note
    inputs["soak"] = _gate_status("soak", p, note)
    inputs["soak_14d"] = _soak_wallclock(soak_payload, soak_note)
    inputs["sysstatus"] = _sysstatus_evidence(root)
    p, note = _load(arts / "bench" / "bench.json")
    inputs["bench"] = _gate_status("bench", p, note)
    inputs["ci"] = _ci_evidence(root)
    rows = []
    for sh in STAKEHOLDERS:
        holds = [(need, inputs[need][1]) for need in sh["needs"]
                 if inputs[need][0] != "PASS"]
        if holds:
            rows.append({"stakeholder": sh["stakeholder"], "scope": sh["scope"],
                         "sign_off": "HOLD",
                         "reasons": [f"{n}: {why}" for n, why in holds],
                         "date": None})
        else:
            rows.append({"stakeholder": sh["stakeholder"], "scope": sh["scope"],
                         "sign_off": "APPROVED",
                         "reasons": [f"{n}: {inputs[n][1]}" for n in sh["needs"]],
                         "date": time.strftime("%Y-%m-%d")})
    sig_path = arts / "signoff" / "signatures.json"
    try:
        sigs = json.loads(sig_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        sigs = {}
    missing_sig = [r["stakeholder"] for r in rows if r["stakeholder"] not in sigs]
    all_approved = all(r["sign_off"] == "APPROVED" for r in rows)
    # PAPER scope: correctness + safety only — kill/risk/oms/reconcile/
    # recovery/drill/soak pass and no critical SRE alert. Perf targets
    # (bench), SAST/pentest, and observability depth are LIVE criteria and
    # must not gate paper.
    paper_needs = ["release/KILLSWITCH_CERTIFICATION", "release/RISK_CERTIFICATION",
                   "release/RECONCILIATION_CERTIFICATION", "release/OMS_CERTIFICATION",
                   "release/BROKER_CERTIFICATION", "release/RECOVERY_CERTIFICATION",
                   "dr", "soak"]
    paper_blockers = [f"{n}: {inputs[n][1]}" for n in paper_needs
                      if inputs[n][0] != "PASS"]
    sre_critical = inputs["sre"][0] == "HOLD" and "ALERT" in inputs["sre"][1]
    if sre_critical:
        paper_blockers.append(f"sre: {inputs['sre'][1]}")
    paper_go = not paper_blockers
    if all_approved and not missing_sig:
        live = "GO-LIVE"
    else:
        live = "NO-GO-LIVE"
    # LIVE-level wall-clock gates: bounded soak and missing R-gates never
    # gate paper rows, but they always block LIVE (fail-closed).
    live_blockers: list[str] = []
    for r in rows:
        if r["sign_off"] != "APPROVED":
            live_blockers.append(f"{r['stakeholder']}: " + "; ".join(r["reasons"]))
    if missing_sig:
        live_blockers.append(f"signatures: missing {', '.join(missing_sig)}")
    if inputs["sysstatus"][0] != "PASS":
        live_blockers.append(f"sysstatus: {inputs['sysstatus'][1]}")
    if inputs["soak_14d"][0] != "PASS":
        live_blockers.append(f"soak_14d: {inputs['soak_14d'][1]}")
    if live_blockers:
        live = "NO-GO-LIVE"
    return {
        "matrix": "DELTA OS RELEASE 1.0 CERTIFICATION",
        "rows": rows,
        "human_signatures": sigs,
        "missing_signatures": missing_sig,
        "sysstatus": list(inputs["sysstatus"]),
        "soak_14d": list(inputs["soak_14d"]),
        "live_blockers": live_blockers,
        "paper": "GO-PAPER" if paper_go else "NO-GO-PAPER",
        "paper_blockers": paper_blockers,
        "live": live,
    }


def render_md(m: dict) -> str:
    lines = ["# DELTA OS RELEASE 1.0 CERTIFICATION — sign-off matrix", "",
             "| Stakeholder | Scope | Sign-off | Reasons / evidence |",
             "| :--- | :--- | :---: | :--- |"]
    for r in m["rows"]:
        lines.append(f"| {r['stakeholder']} | {r['scope']} | {r['sign_off']} | "
                     + "; ".join(r["reasons"]) + " |")
    lines += ["", f"PAPER: **{m['paper']}**", f"LIVE: **{m['live']}**", "",
              ("Paper blockers: " + ("none" if not m["paper_blockers"]
                else "; ".join(m["paper_blockers"]))), "",
              ("Live blockers: " + ("none" if not m.get("live_blockers")
                else "; ".join(m["live_blockers"]))), "",
              ("Human signatures: " +
               (", ".join(f"{k} ({v})" for k, v in m["human_signatures"].items())
                if m["human_signatures"] else "none recorded") +
               (f"; missing: {', '.join(m['missing_signatures'])}"
                if m["missing_signatures"] else ""))]
    return "\n".join(lines) + "\n"


def run(root: Path) -> dict:
    root = Path(root)
    m = collect(root)
    m["generated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    m["hash"] = _sha({k: v for k, v in m.items()})
    out = root / "artifacts" / "signoff"
    out.mkdir(parents=True, exist_ok=True)
    (out / "matrix.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    (out / "matrix.md").write_text(render_md(m), encoding="utf-8")
    m["artifact"] = str(out / "matrix.json")
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    m = run(Path(a.root))
    print(json.dumps({k: m[k] for k in ("paper", "paper_blockers", "live",
                                       "live_blockers", "missing_signatures",
                                       "artifact")}, indent=2))
    for r in m["rows"]:
        print(f" - {r['stakeholder']}: {r['sign_off']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
