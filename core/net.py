"""Small audited network helpers: scheme-enforced HTTP(S) opening.

B310 triage (P0-6): every outbound call in the repo must refuse non-http(s)
schemes (file:/, custom handlers) explicitly instead of relying on audit
warnings. Timeouts stay at the call site.
"""
from __future__ import annotations

from typing import Union
from urllib.parse import urlsplit
import urllib.request

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def checked_url(url_or_request: Union[str, urllib.request.Request]) -> str:
    """Return the URL string after enforcing the http(s) scheme.

    Raises ValueError on any other scheme (fail closed).
    """
    url = (url_or_request.get_full_url()
           if isinstance(url_or_request, urllib.request.Request)
           else url_or_request)
    scheme = urlsplit(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"refusing non-http(s) URL (scheme={scheme!r})")
    return url


def urlopen_checked(url_or_request: Union[str, urllib.request.Request],
                    **kwargs):
    """urllib.request.urlopen with mandatory http(s) scheme enforcement."""
    checked_url(url_or_request)
    # nosec B310: scheme allow-list enforced by checked_url() immediately
    # above; this is the single audited call site for the whole repo.
    return urllib.request.urlopen(url_or_request, **kwargs)  # nosec B310


__all__ = ["checked_url", "urlopen_checked"]
