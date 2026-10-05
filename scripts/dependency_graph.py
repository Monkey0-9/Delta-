"""Group 01 — Automated architecture dependency graph (import-lint).

Scans python imports, reports reverse edges (domain -> delta_tui).
"""
from __future__ import annotations

import ast
from pathlib import Path


def edges(root: str = ".") -> list[tuple[str, str]]:
    out = []
    for p in Path(root).rglob("*.py"):
        if ".venv" in str(p) or "__pycache__" in str(p):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module:
                out.append((str(p), n.module))
    return out


def reverse_edges(root: str = ".") -> list[tuple[str, str]]:
    rev = []
    for f, mod in edges(root):
        if mod.startswith("delta_tui") and not f.startswith("delta_tui") and not f.startswith("apps"):
            rev.append((f, mod))
    return rev


if __name__ == "__main__":
    bad = reverse_edges(".")
    print(f"reverse edges: {len(bad)}")
    for f, m in bad[:20]:
        print(f"  {f} -> {m}")
