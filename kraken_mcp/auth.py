from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
from typing import Any


def _nonce() -> str:
    return str(int(time.time() * 1000))


def sign_spot_request(uri_path: str, data: dict[str, Any], secret: str) -> dict[str, str]:
    """Return headers dict containing API-Sign for a Spot private request."""
    nonce = _nonce()
    data["nonce"] = nonce
    post_data = urllib.parse.urlencode(data)

    message = (nonce + post_data).encode()
    sha256_digest = hashlib.sha256(message).digest()
    hmac_message = uri_path.encode() + sha256_digest
    signature = base64.b64encode(
        hmac.new(base64.b64decode(secret), hmac_message, hashlib.sha512).digest()
    ).decode()

    return {"API-Sign": signature}


def sign_futures_request(
    endpoint_path: str,
    post_data: str,
    secret: str,
) -> tuple[str, dict[str, str]]:
    """Return (nonce, headers) for a Futures private request.

    endpoint_path: path after /derivatives prefix, e.g. '/api/v3/sendorder'
    post_data: URL-encoded body string (may be empty string for GET)
    """
    nonce = _nonce()
    message = (post_data + nonce + endpoint_path).encode()
    sha256_digest = hashlib.sha256(message).digest()
    signature = base64.b64encode(
        hmac.new(base64.b64decode(secret), sha256_digest, hashlib.sha512).digest()
    ).decode()

    return nonce, {
        "APIKey": "",  # caller fills in api_key
        "Nonce": nonce,
        "Authent": signature,
    }


def sign_futures_ws_challenge(challenge: str, secret: str) -> str:
    """Sign a WS challenge. Returns signed_challenge string."""
    sha256_digest = hashlib.sha256(challenge.encode()).digest()
    return base64.b64encode(
        hmac.new(base64.b64decode(secret), sha256_digest, hashlib.sha512).digest()
    ).decode()
