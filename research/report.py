"""Research report generation: deterministic markdown from validated artifacts."""
from __future__ import annotations


def render_research_report(
    *,
    title: str,
    hypothesis: str,
    experiment_id: str,
    manifest_hash: str,
    metrics: dict,
    stress: dict,
    gates: dict,
    limitations: tuple[str, ...] = (),
) -> str:
    if not title.strip() or not experiment_id.strip():
        raise ValueError("title and experiment_id required.")
    lines = [
        f"# {title}",
        "",
        f"Experiment: `{experiment_id}`",
        f"Manifest: `{manifest_hash}`",
        "",
        "## Hypothesis",
        hypothesis,
        "",
        "## Metrics",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(metrics.items())]
    lines += ["", "## Stress"]
    lines += [f"- {k}: {v}" for k, v in sorted(stress.items())]
    lines += ["", "## Gates"]
    lines += [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in sorted(gates.items())]
    if limitations:
        lines += ["", "## Limitations"]
        lines += [f"- {item}" for item in limitations]
    lines.append("")
    return "\n".join(lines)
