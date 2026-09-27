"""python -m delta_os — launch the terminal."""
import delta_compat  # noqa: F401  (blueprint delta.* import alias)
from delta_os.repl import Terminal

if __name__ == "__main__":
    raise SystemExit(Terminal().run())
