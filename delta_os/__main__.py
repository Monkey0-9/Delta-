"""python -m delta_os — launch the terminal."""
import sys


def main() -> int:
    try:
        import delta_compat  # noqa: F401  (blueprint delta.* import alias)
        from delta_os.repl import Terminal
        return Terminal().run()
    except Exception as exc:
        # Fail-closed delivery: an AuditTamperError (raised at import or boot
        # when the ledger fails integrity) halts LOUD with a non-zero exit
        # naming file/line instead of a bare traceback. Type-name check (not
        # isinstance) because the audit import itself may be what raised.
        if type(exc).__name__ == "AuditTamperError":
            print(f"DELTA HALTED: audit ledger tamper — refusing to boot: {exc}",
                  file=sys.stderr)
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())
