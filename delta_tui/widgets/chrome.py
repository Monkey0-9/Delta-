"""Rich widgets — every widget takes a TYPED viewmodel, never raw strings."""
from __future__ import annotations


def header_text(h: dict) -> str:
    return (f"DELTA | {h.get('workspace','home').upper()} | "
            f"{h.get('mode')} | DATA:{h.get('data')} | MODEL:{h.get('model')} | "
            f"BROKER:{h.get('broker')} | KILL:{h.get('kill')}")


def status_text(s: dict) -> str:
    return (f"DATA {s.get('data')} | MODEL {s.get('model')} | "
            f"BROKER {s.get('broker')} | KILL SWITCH {s.get('kill')}")
