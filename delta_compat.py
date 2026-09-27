"""Blueprint-era import compatibility: maps phantom `delta.*` to real top-level packages.

Dozens of blueprint files `from delta.X import ...` while the repo's packages
live at top level (`data/`, `core/`, ...). This MetaPathFinder aliases
`delta.<rest>` -> `<rest>` so those imports resolve to the ONE real module
object (no dual execution, isinstance-safe).

Install once at process entry BEFORE any blueprint import:
    import delta_compat  # noqa: F401  (side effect: installs finder)
Root conftest.py does this for pytest; production entry points
(delta_os.__main__, scripts) do it explicitly.
"""
from __future__ import annotations

import importlib
import importlib.abc
import sys

ALIAS_PREFIX = "delta."


class _DeltaAliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "delta" or fullname.startswith(ALIAS_PREFIX):
            import importlib.machinery

            return importlib.machinery.ModuleSpec(fullname, self,
                                                  is_package=(fullname == "delta"))
        return None

    def create_module(self, spec):
        return None  # default module creation; see exec_module

    def exec_module(self, module):
        name = module.__name__
        if name == "delta":
            module.__path__ = []
            module.__doc__ = "Alias root: delta.X resolves to top-level package X."
            return
        real = name[len(ALIAS_PREFIX):]
        try:
            real_mod = importlib.import_module(real)
        except ImportError as exc:
            raise ImportError(
                f"{name}: blueprint alias target {real!r} does not exist. "
                f"Implement the real module or fix the import.") from exc
        sys.modules[name] = real_mod


def install() -> None:
    for f in sys.meta_path:
        if isinstance(f, _DeltaAliasFinder):
            return
    sys.meta_path.insert(0, _DeltaAliasFinder())


install()

__all__ = ["install"]
