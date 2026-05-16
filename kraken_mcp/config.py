from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


@dataclass
class Config:
    spot_api_key: str | None
    spot_api_secret: str | None
    futures_api_key: str | None
    futures_api_secret: str | None
    futures_env: Literal["live", "demo"]
    trading_enabled: bool
    transfers_enabled: bool
    spot_rate_limit_tier: Literal["starter", "intermediate", "pro"]
    http_timeout_seconds: float
    log_level: str

    @property
    def spot_base_url(self) -> str:
        return "https://api.kraken.com"

    @property
    def futures_base_url(self) -> str:
        if self.futures_env == "demo":
            return "https://demo-futures.kraken.com"
        return "https://futures.kraken.com"

    @property
    def futures_ws_url(self) -> str:
        if self.futures_env == "demo":
            return "wss://demo-futures.kraken.com/ws/v1"
        return "wss://futures.kraken.com/ws/v1"

    @property
    def has_spot_auth(self) -> bool:
        return bool(self.spot_api_key and self.spot_api_secret)

    @property
    def has_futures_auth(self) -> bool:
        return bool(self.futures_api_key and self.futures_api_secret)


def load_config() -> Config:
    futures_env = os.getenv("KRAKEN_FUTURES_ENV", "live")
    if futures_env not in ("live", "demo"):
        raise ValueError(f"KRAKEN_FUTURES_ENV must be 'live' or 'demo', got '{futures_env}'")

    tier = os.getenv("KRAKEN_SPOT_RATE_LIMIT_TIER", "intermediate")
    if tier not in ("starter", "intermediate", "pro"):
        raise ValueError(f"KRAKEN_SPOT_RATE_LIMIT_TIER must be starter/intermediate/pro, got '{tier}'")

    cfg = Config(
        spot_api_key=os.getenv("KRAKEN_SPOT_API_KEY") or None,
        spot_api_secret=os.getenv("KRAKEN_SPOT_API_SECRET") or None,
        futures_api_key=os.getenv("KRAKEN_FUTURES_API_KEY") or None,
        futures_api_secret=os.getenv("KRAKEN_FUTURES_API_SECRET") or None,
        futures_env=futures_env,  # type: ignore[arg-type]
        trading_enabled=os.getenv("KRAKEN_TRADING_ENABLED", "false").lower() == "true",
        transfers_enabled=os.getenv("KRAKEN_TRANSFERS_ENABLED", "false").lower() == "true",
        spot_rate_limit_tier=tier,  # type: ignore[arg-type]
        http_timeout_seconds=float(os.getenv("KRAKEN_HTTP_TIMEOUT_SECONDS", "30")),
        log_level=os.getenv("KRAKEN_LOG_LEVEL", "INFO").upper(),
    )

    # Warn on incomplete key pairs
    import logging
    log = logging.getLogger(__name__)
    if bool(cfg.spot_api_key) != bool(cfg.spot_api_secret):
        log.warning("Spot API key/secret pair is incomplete — private spot tools will fail")
    if bool(cfg.futures_api_key) != bool(cfg.futures_api_secret):
        log.warning("Futures API key/secret pair is incomplete — private futures tools will fail")

    return cfg
