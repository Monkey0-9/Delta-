"""Group 04/10 — Session manager: new/resume/fork/export/search/persist.

SQLite-backed, survives restart. Risk state isolated per session in SIM.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionMeta:
    session_id: str
    mode: str
    universe: str = ""
    mandate_hash: str = ""
    created_at: float = 0.0


def _db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute(
        "CREATE TABLE IF NOT EXISTS sessions"
        "(id TEXT PRIMARY KEY, mode TEXT, universe TEXT, mandate_hash TEXT,"
        " created_at REAL, data TEXT)"
    )
    return con


class SessionManager:
    def __init__(self, db_path: str = "data/sessions.sqlite") -> None:
        self.db_path = Path(db_path)

    def new(self, mode: str = "PAPER", universe: str = "") -> SessionMeta:
        import random
        con = _db(self.db_path)
        try:
            for _ in range(5):
                sid = f"sess-{int(time.time()*1000):x}-{random.randint(0, 0xFFFF):04x}"
                meta = SessionMeta(sid, mode, universe, "", time.time())
                try:
                    con.execute(
                        "INSERT INTO sessions VALUES (?,?,?,?,?,?)",
                        (sid, mode, universe, "", meta.created_at, json.dumps({})),
                    )
                    con.commit()
                    return meta
                except sqlite3.IntegrityError:
                    continue
            raise RuntimeError("session id collision")
        finally:
            con.close()

    def fork(self, session_id: str) -> SessionMeta:
        con = _db(self.db_path)
        try:
            row = con.execute(
                "SELECT mode, universe, mandate_hash, data FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"unknown session {session_id}")
            mode, universe, mhash, data = row
            nxt = self.new(mode, universe)
            con2 = _db(self.db_path)
            try:
                con2.execute(
                    "UPDATE sessions SET mandate_hash=?, data=? WHERE id=?", (mhash, data, nxt.session_id)
                )
                con2.commit()
            finally:
                con2.close()
            nxt.mandate_hash = mhash or ""
            return nxt
        finally:
            con.close()

    def export(self, session_id: str) -> dict:
        con = _db(self.db_path)
        try:
            row = con.execute(
                "SELECT mode, universe, mandate_hash, created_at, data"
                " FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
            if not row:
                raise KeyError(f"unknown session {session_id}")
            mode, universe, mhash, created, data = row
            return {
                "session_id": session_id, "mode": mode, "universe": universe,
                "mandate_hash": mhash, "created_at": created,
                "data": json.loads(data or "{}"),
            }
        finally:
            con.close()

    def search(self, query: str) -> list[str]:
        con = _db(self.db_path)
        try:
            rows = con.execute("SELECT id, universe FROM sessions").fetchall()
            q = (query or "").lower()
            return [sid for sid, uni in rows if q in sid.lower() or q in (uni or "").lower()]
        finally:
            con.close()

    @staticmethod
    def mandate_hash(mandate: dict) -> str:
        blob = json.dumps(mandate, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def rename(self, session_id: str, universe: str) -> None:
        con = _db(self.db_path)
        try:
            con.execute("UPDATE sessions SET universe=? WHERE id=?", (universe, session_id))
            con.commit()
        finally:
            con.close()

    def set_mandate(self, session_id: str, mandate: dict) -> str:
        h = self.mandate_hash(mandate)
        con = _db(self.db_path)
        try:
            con.execute("UPDATE sessions SET mandate_hash=?, data=? WHERE id=?",
                        (h, json.dumps({"mandate": mandate}), session_id))
            con.commit()
        finally:
            con.close()
        return h

    def diff(self, a: str, b: str) -> dict:
        ea, eb = self.export(a), self.export(b)
        return {"mandate_drift": ea["mandate_hash"] != eb["mandate_hash"],
                "universe_a": ea["universe"], "universe_b": eb["universe"]}

    def retention(self, max_age_days: int = 90) -> int:
        cutoff = time.time() - max_age_days * 86400
        con = _db(self.db_path)
        try:
            cur = con.execute("DELETE FROM sessions WHERE created_at<?", (cutoff,))
            con.commit()
            return cur.rowcount
        finally:
            con.close()
