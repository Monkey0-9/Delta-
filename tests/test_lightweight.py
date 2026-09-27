"""Lightweight mandate: import budgets + dependency discipline.

Python is thin glue; C/C++/Rust own the hot loops. Rules enforced here:
1. `import delta_os` must not import pandas/numpy/httpx/yfinance/cryptography
   (lazy package; submodules import heavy deps at use-site or top of the
   submodule that genuinely needs them).
2. Bare `import delta_os` completes quickly (subprocess wall budget).
3. Native accelerators stay loadable (accel backend != crash).
4. `import core` resolves to real sibling modules (no phantom `delta.*` package).
"""
from __future__ import annotations

import subprocess
import sys
import time

BUDGET_S = 2.0
FORBIDDEN_AT_PACKAGE_IMPORT = ("pandas", "numpy", "httpx", "yfinance",
                               "cryptography", "reportlab")


def _fresh_imports(code: str) -> list[str]:
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd="C:\\Delta", timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    return r.stdout.strip().split()


def test_delta_os_package_import_is_light():
    mods = _fresh_imports(
        "import sys, delta_os; print(' '.join(sorted(sys.modules)))")
    offenders = [m for m in FORBIDDEN_AT_PACKAGE_IMPORT
                 if m in mods or any(k == m or k.startswith(m + ".") for k in mods)]
    assert not offenders, f"heavy deps at package import: {offenders}"
    import delta_os  # noqa: F401  (in-process sanity; budget checked fresh below)
    assert set(dir(delta_os)) >= {"repl", "vault", "safety"}
    _ = delta_os.repl.Terminal  # lazy load works


def test_native_backends_load_without_crash():
    from native import accel
    from native import lob

    assert accel.backend() in ("rust", "c", "numpy")
    assert isinstance(lob.available(), bool)


def test_core_package_resolves():
    import core

    for name in ("Config", "Vault", "EventBus", "PluginManager", "ModelRegistry",
                 "BrokerRegistry"):
        assert name in core.__all__
        assert getattr(core, name, None) is not None


def test_fresh_interpreter_import_budget():
    code = "import time; t0=time.perf_counter(); import delta_os; print(time.perf_counter()-t0)"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd="C:\\Delta", timeout=120)
    assert r.returncode == 0, r.stderr[-500:]
    assert float(r.stdout.strip()) < BUDGET_S
