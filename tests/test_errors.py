import pytest

from kraken_mcp.errors import (
    normalize_spot_response,
    normalize_futures_response,
    error_response,
)


def test_spot_success():
    body = {"error": [], "result": {"XXBTZUSD": {"a": ["50000"]}}}
    result = normalize_spot_response(body, 200, 15, 0.0)
    assert result["ok"] is True
    assert result["errors"] == []
    assert "XXBTZUSD" in result["data"]


def test_spot_kraken_error():
    body = {"error": ["EAPI:Invalid key"], "result": {}}
    result = normalize_spot_response(body, 200, 15, 0.0)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "auth_failed"


def test_spot_http_error():
    body = {"error": []}
    result = normalize_spot_response(body, 429, 0, 5.0)
    assert result["ok"] is False


def test_futures_success():
    body = {"result": "success", "accounts": {"cash": {"balances": {}}}}
    result = normalize_futures_response(body, 200, 490, 0.1)
    assert result["ok"] is True
    assert result["errors"] == []


def test_futures_error():
    body = {"result": "error", "error": "apiLimitExceeded"}
    result = normalize_futures_response(body, 200, 0, 10.0)
    assert result["ok"] is False
    assert result["errors"][0]["code"] == "rate_limited"


def test_error_response_helper():
    r = error_response("disabled_by_config", "Trading disabled")
    assert r["ok"] is False
    assert r["errors"][0]["code"] == "disabled_by_config"
