"""DELTA OS alert fan-out: terminal log + audit + messengers. Default OFF.

Terminal toast/log + compliance record always fire. Telegram/WhatsApp fire
only when vault credentials exist; otherwise the channel reports UNAVAILABLE
(never silent, never fake-sent). Messenger failures are recorded, never raise.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field

from core.net import urlopen_checked


@dataclass
class FanoutResult:
    terminal: bool = False
    audit: bool = False
    telegram: str = "UNCONFIGURED"
    whatsapp: str = "UNCONFIGURED"
    errors: list = field(default_factory=list)


def _post_json(url: str, payload: dict, token: str = "",
               timeout_s: float = 10.0) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urlopen_checked(req, timeout=timeout_s) as resp:
        return {"http": resp.status, "body": resp.read(512).decode("utf-8", "replace")}


def send_telegram(bot_token: str, chat_id: str, text: str) -> dict:
    """Telegram Bot API sendMessage. Raises on failure."""
    if not bot_token or not chat_id:
        raise ValueError("telegram unconfigured (need bot token + chat id).")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    out = _post_json(url, {"chat_id": chat_id, "text": text[:4000]})
    if out.get("http") != 200:
        raise RuntimeError(f"telegram HTTP {out.get('http')}: {out.get('body')}")
    return out


def send_whatsapp(token: str, phone_number_id: str, to: str, text: str) -> dict:
    """Meta WhatsApp Cloud API text message. Raises on failure."""
    if not token or not phone_number_id or not to:
        raise ValueError("whatsapp unconfigured (need token + phone id + recipient).")
    url = (f"https://graph.facebook.com/v21.0/{phone_number_id}"
           "/messages")
    out = _post_json(url, {"messaging_product": "whatsapp", "to": to,
                           "type": "text", "text": {"body": text[:4000]}},
                     token=token)
    if out.get("http") != 200:
        raise RuntimeError(f"whatsapp HTTP {out.get('http')}: {out.get('body')}")
    return out


def _format(alert: dict) -> str:
    ts = str(alert.get("timestamp", ""))[11:19]
    return f"[DELTA {alert.get('level', '?')}] {alert.get('event', '?')} {ts}: {alert.get('message', '')}"


class AlertFanout:
    """Broadcast one alert dict to every configured channel."""

    def __init__(self, vault=None, compliance=None, terminal_log=None):
        self.vault = vault
        self.compliance = compliance
        self.terminal_log = terminal_log if terminal_log is not None else []

    def _creds(self, slot: str) -> dict:
        try:
            if self.vault is None or getattr(self.vault, "locked", True):
                return {}
            return dict(self.vault.get(slot) or {})
        except Exception:
            return {}

    def broadcast(self, alert: dict) -> FanoutResult:
        res = FanoutResult()
        text = _format(alert)
        self.terminal_log.append(text)
        res.terminal = True
        if self.compliance is not None:
            try:
                self.compliance.append("report", {"alert": alert})
                res.audit = True
            except Exception as exc:
                res.errors.append(f"audit FAILED: {exc}")
        tg = self._creds("telegram")
        if tg.get("bot_token") and tg.get("chat_id"):
            try:
                send_telegram(tg["bot_token"], tg["chat_id"], text)
                res.telegram = "SENT"
            except Exception as exc:
                res.telegram = "FAILED"
                res.errors.append(f"telegram FAILED: {exc}")
        wa = self._creds("whatsapp")
        if wa.get("token") and wa.get("phone_number_id") and wa.get("to"):
            try:
                send_whatsapp(wa["token"], wa["phone_number_id"], wa["to"], text)
                res.whatsapp = "SENT"
            except Exception as exc:
                res.whatsapp = "FAILED"
                res.errors.append(f"whatsapp FAILED: {exc}")
        return res


__all__ = ["FanoutResult", "AlertFanout", "send_telegram", "send_whatsapp"]
