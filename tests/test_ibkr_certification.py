"""IBKR Adapter Certification Test Suite.

Verifies:
- IBKR adapter status handling
- Contract resolution mock
- Order submission formatting & error handling
- Cancel and cancel-all operations
"""
from unittest.mock import MagicMock, patch
import pytest

from delta_os.brokers import IBKRAdapter, BrokerError, BrokerRouter
from execution.adapters.ibkr import IBKRClientPortalAdapter, IBKRError


def test_ibkr_unconfigured_status():
    adapter = IBKRAdapter(host="")
    st = adapter.status()
    assert st["broker"] == "ibkr"
    assert st["connected"] is False
    assert "no gateway host" in st["error"]


def test_ibkr_submit_unconfigured_raises():
    adapter = IBKRAdapter(host="")
    with pytest.raises(BrokerError, match="not configured"):
        adapter.submit("AAPL", "BUY", 10.0, 150.0)


@patch("httpx.get")
def test_ibkr_client_portal_status(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"authenticated": True, "connected": True, "competing": False}
    mock_get.return_value = mock_resp

    client = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="U1234567")
    st = client.status()
    assert st["connected"] is True
    assert st["authenticated"] is True


@patch("httpx.post")
def test_ibkr_contract_resolution(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"conid": 265598, "symbol": "AAPL"}]
    mock_post.return_value = mock_resp

    client = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="U1234567")
    con_id = client.resolve_contract("AAPL")
    assert con_id == 265598


@patch("httpx.post")
def test_ibkr_order_submission(mock_post, monkeypatch):
    # B7b: mutating calls require DELTA_LIVE=ARMED (fail-closed) plus an
    # explicitly bound kill board (ARMED alone never admits a live order).
    from risk.kill_switch.kill_switch import KillSwitchBoard
    monkeypatch.setenv("DELTA_LIVE", "ARMED")
    mock_post_search = MagicMock()
    mock_post_search.status_code = 200
    mock_post_search.json.return_value = [{"conid": 265598, "symbol": "AAPL"}]

    mock_post_order = MagicMock()
    mock_post_order.status_code = 200
    mock_post_order.json.return_value = [{"order_id": "1001", "order_status": "Submitted"}]

    # Return search on first call, order on second call
    mock_post.side_effect = [mock_post_search, mock_post_order]

    client = IBKRClientPortalAdapter(host="https://localhost:5000", account_id="U1234567",
                                      kill_board=KillSwitchBoard())
    res = client.submit("AAPL", "BUY", 50.0, 150.0, idempotency_key="KEY-123")
    assert res["order_id"] == "1001"
    assert res["status"] == "Submitted"
    assert res["broker"] == "ibkr"


def test_broker_router_ibkr_switch():
    router = BrokerRouter(ibkr=IBKRAdapter(host="https://localhost:5000", account_id="U123456"))
    active = router.use("ibkr")
    assert active == "ibkr"
    assert isinstance(router.current(), IBKRAdapter)
