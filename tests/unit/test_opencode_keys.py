"""OpenCode-parity keybindings: Ctrl+C cancels text, quits on empty line."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _term():
    from trader.opencode_terminal import OpenCodeTerminal
    return OpenCodeTerminal(backend=MagicMock())


def _handler(term, *keys):
    from prompt_toolkit.keys import Keys
    want = tuple(keys)
    for b in term._build_keybindings().bindings:
        if tuple(b.keys) == want:
            return b.handler
    raise AssertionError(f"no binding for {want}.")


class _Buf:
    def __init__(self, text=""):
        self.text = text
        self.reset_called = False

    def reset(self):
        self.reset_called = True
        self.text = ""

    def insert_text(self, s):
        self.text += s


class _App:
    def __init__(self, text=""):
        self.current_buffer = _Buf(text)
        self.result = None

    def exit(self, result=None, exception=None):
        if exception is not None:
            raise exception
        self.result = result


def test_ctrl_c_cancels_nonempty_line():
    from prompt_toolkit.keys import Keys
    term = _term()
    app = _App("buy SPY")
    _handler(term, Keys.ControlC)(SimpleNamespace(app=app))
    assert app.current_buffer.reset_called
    assert term._turn_cancelled is True


def test_ctrl_c_quits_on_empty_line():
    from prompt_toolkit.keys import Keys
    term = _term()
    with pytest.raises(KeyboardInterrupt):
        _handler(term, Keys.ControlC)(SimpleNamespace(app=_App("   ")))


def test_enter_submits_and_esc_enter_newlines():
    from prompt_toolkit.keys import Keys
    term = _term()
    app = _App("hello")
    _handler(term, Keys.ControlM)(SimpleNamespace(app=app))
    assert app.result == "hello"
    app2 = _App("a")
    _handler(term, Keys.Escape, Keys.ControlM)(SimpleNamespace(app=app2))
    assert app2.current_buffer.text == "a\n"
