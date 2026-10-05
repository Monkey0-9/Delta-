"""G12 — PIT gate: 5-stamp enforcement + dataset SHA + reproduce helper.

t_event<=t_published<=t_available<=t_decision<=t_execution enforced.
"""
from __future__ import annotations

import hashlib
import json


def check_chain(t_event: float, t_pub: float, t_avail: float, t_dec: float, t_exec: float) -> None:
    if not (t_event <= t_pub <= t_avail <= t_dec <= t_exec):
        raise ValueError("PIT chain violated: t_event<=t_pub<=t_avail<=t_dec<=t_exec required")


def dataset_sha(records: list[dict]) -> str:
    blob = json.dumps(records, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()


def reproduce_manifest(exp_id: str, code_sha: str, dataset_sha_: str,
                       records: list[dict] | None = None) -> dict:
    """P-1.5: replay-exactness is VERIFIED, never asserted.

    With ``records`` supplied, the dataset hash is recomputed and compared;
    ``replays_pit_exactly`` is True only on match. Without records there is
    nothing to verify against, so it is False with an explicit reason —
    previously this returned a constant True.
    """
    if records is None:
        return {"exp_id": exp_id, "code_sha": code_sha,
                "dataset_sha": dataset_sha_, "replays_pit_exactly": False,
                "reason": "unverified: no records supplied for hash recompute"}
    recomputed = dataset_sha(records)
    ok = recomputed == dataset_sha_
    out = {"exp_id": exp_id, "code_sha": code_sha,
           "dataset_sha": dataset_sha_, "replays_pit_exactly": ok}
    if not ok:
        out["reason"] = "dataset hash mismatch on recompute"
    return out
