"""W102 reproducibility/governance + W103 observability (light, file-based)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "uncommitted"


@dataclass
class RunManifest:
    run_id: str
    question: str
    seed: int
    data_hashes: dict
    feature_version: str
    model_version: str
    prompt_version: str
    code_commit: str
    config: dict
    results: dict
    started_at: str = ""
    duration_ms: float = 0.0

    def fingerprint(self) -> str:
        raw = json.dumps({"q": self.question, "seed": self.seed, "d": self.data_hashes,
                          "f": self.feature_version, "m": self.model_version,
                          "p": self.prompt_version, "c": self.code_commit,
                          "cfg": self.config, "r": self.results}, sort_keys=True, default=str)
        return "RUN-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def save_manifest(m: RunManifest, root: str = "artifacts/real_loop") -> Path:
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    fp = p / f"{m.run_id}.manifest.json"
    fp.write_text(json.dumps({**m.__dict__, "fingerprint": m.fingerprint()},
                             indent=2, sort_keys=True, default=str), encoding="utf-8")
    return fp


@dataclass
class ObsLog:
    events: list[dict] = field(default_factory=list)

    def event(self, stage: str, msg: str, **kw) -> None:
        self.events.append({"t": datetime.now(timezone.utc).isoformat(), "stage": stage,
                            "msg": msg, **kw})

    def metrics(self) -> dict:
        stages = {}
        for e in self.events:
            stages[e["stage"]] = stages.get(e["stage"], 0) + 1
        return {"n_events": len(self.events), "by_stage": stages}


# ---- research memory (episodic, JSONL) ----
def append_memory(kind: str, record: dict, root: str = "artifacts/real_loop/memory") -> Path:
    p = Path(root)
    p.mkdir(parents=True, exist_ok=True)
    fp = p / f"{kind}.jsonl"
    with fp.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": datetime.now(timezone.utc).isoformat(), **record},
                           default=str) + "\n")
    return fp
