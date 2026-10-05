"""Group 07 — Deep-link: selecting alpha opens lineage graph (Enter)."""
from __future__ import annotations


def alpha_lineage(alpha_id: str, store) -> str:
    lineage = f"alpha {alpha_id}: features -> neutralization -> validation (see Alpha screen)"
    try:
        from delta_tui.widgets.modal import ModalManager
        ModalManager().inspect_alpha(alpha_id, lineage)
    except Exception:
        pass
    return lineage
