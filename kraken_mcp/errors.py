from __future__ import annotations

from typing import Any


class KrakenError(Exception):
    def __init__(self, code: str, message: str, raw_status: int = 0):
        super().__init__(message)
        self.code = code
        self.raw_status = raw_status


class NotConfiguredError(KrakenError):
    def __init__(self, message: str):
        super().__init__("not_configured", message, 0)


class DisabledByConfigError(KrakenError):
    def __init__(self, gate: str):
        super().__init__("disabled_by_config", f"Gate '{gate}' is disabled. Set {gate} env var to enable.", 0)


# Maps Kraken error strings to stable MCP codes
_SPOT_ERROR_MAP: dict[str, str] = {
    "EAPI:Invalid key": "auth_failed",
    "EAPI:Invalid signature": "auth_failed",
    "EAPI:Invalid nonce": "auth_failed",
    "EOrder:Insufficient funds": "insufficient_funds",
    "EGeneral:Permission denied": "permission_denied",
    "EAPI:Rate limit exceeded": "rate_limited",
    "EService:Unavailable": "upstream_unavailable",
    "EService:Busy": "upstream_unavailable",
}

_FUTURES_ERROR_MAP: dict[str, str] = {
    "apiLimitExceeded": "rate_limited",
    "authenticationError": "auth_failed",
    "insufficientFunds": "insufficient_funds",
    "Unknown": "upstream_error",
}


def _map_spot_error(kraken_error: str) -> str:
    for prefix, code in _SPOT_ERROR_MAP.items():
        if kraken_error.startswith(prefix):
            return code
    return "kraken_error"


def _map_futures_error(kraken_error: str) -> str:
    return _FUTURES_ERROR_MAP.get(kraken_error, "kraken_error")


def normalize_spot_response(
    body: dict[str, Any],
    raw_status: int,
    rate_limit_remaining: int,
    rate_limit_reset_s: float,
) -> dict[str, Any]:
    kraken_errors = body.get("error", [])
    ok = raw_status == 200 and not kraken_errors
    errors = [
        {"code": _map_spot_error(e), "message": e}
        for e in kraken_errors
    ]
    if not ok and not errors:
        errors = [{"code": "http_error", "message": f"HTTP {raw_status}"}]
    return {
        "ok": ok,
        "data": body.get("result"),
        "errors": errors,
        "raw_status": raw_status,
        "rate_limit": {"remaining": rate_limit_remaining, "reset_in_s": rate_limit_reset_s},
    }


def normalize_futures_response(
    body: dict[str, Any],
    raw_status: int,
    rate_limit_remaining: int,
    rate_limit_reset_s: float,
) -> dict[str, Any]:
    result_str = body.get("result", "")
    ok = raw_status == 200 and result_str != "error"
    errors: list[dict[str, str]] = []
    if not ok:
        err_msg = body.get("error", body.get("errors", f"HTTP {raw_status}"))
        if isinstance(err_msg, list):
            errors = [{"code": _map_futures_error(e), "message": e} for e in err_msg]
        elif isinstance(err_msg, str):
            errors = [{"code": _map_futures_error(err_msg), "message": err_msg}]
        else:
            errors = [{"code": "unknown_error", "message": str(err_msg)}]

    data = {k: v for k, v in body.items() if k not in ("result", "error", "errors")}
    if not data:
        data = None  # type: ignore[assignment]

    return {
        "ok": ok,
        "data": data or body,
        "errors": errors,
        "raw_status": raw_status,
        "rate_limit": {"remaining": rate_limit_remaining, "reset_in_s": rate_limit_reset_s},
    }


def error_response(code: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "data": None,
        "errors": [{"code": code, "message": message}],
        "raw_status": 0,
        "rate_limit": {"remaining": 0, "reset_in_s": 0.0},
    }
