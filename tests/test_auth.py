import base64
import hashlib
import hmac
import time
import urllib.parse

import pytest

from kraken_mcp.auth import sign_spot_request, sign_futures_request, sign_futures_ws_challenge


def test_spot_sign_produces_api_sign_header():
    secret = base64.b64encode(b"test_secret_bytes_padded_enough!").decode()
    data = {"pair": "XBTUSD", "type": "buy"}
    headers = sign_spot_request("/0/private/AddOrder", data, secret)
    assert "API-Sign" in headers
    assert "nonce" in data  # sign_spot_request adds nonce in-place


def test_spot_sign_deterministic_given_nonce():
    """Same nonce → same signature."""
    secret = base64.b64encode(b"test_secret_bytes_padded_enough!").decode()
    data1 = {"nonce": "1234567890"}
    data2 = {"nonce": "1234567890"}
    h1 = sign_spot_request("/0/private/Balance", data1, secret)
    h2 = sign_spot_request("/0/private/Balance", data2, secret)
    assert h1["API-Sign"] == h2["API-Sign"]


def test_futures_sign_returns_nonce_and_headers():
    secret = base64.b64encode(b"test_secret_bytes_padded_enough!").decode()
    nonce, headers = sign_futures_request("/api/v3/sendorder", "symbol=PI_XBTUSD", secret)
    assert nonce.isdigit()
    assert "Authent" in headers
    assert "Nonce" in headers


def test_ws_challenge_sign():
    secret = base64.b64encode(b"test_secret_bytes_padded_enough!").decode()
    challenge = "test-challenge-uuid-string"
    signed = sign_futures_ws_challenge(challenge, secret)
    assert isinstance(signed, str)
    assert len(signed) > 0

    # Verify manually
    sha256_digest = hashlib.sha256(challenge.encode()).digest()
    expected = base64.b64encode(
        hmac.new(base64.b64decode(secret), sha256_digest, hashlib.sha512).digest()
    ).decode()
    assert signed == expected
