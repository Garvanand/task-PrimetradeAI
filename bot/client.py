"""
Binance Futures Testnet REST client.

Handles HMAC-SHA256 request signing, timestamping, and HTTP error
mapping.  Every request and response is logged at DEBUG level so the
log file provides a full audit trail.

Production-grade features:
- Retry with exponential backoff for transient failures
- Simple rate limiter (1200 requests/min per Binance docs)
- Comprehensive API coverage (orders, account, positions, ticker, history)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://testnet.binancefuture.com"
TIMEOUT = 10  # seconds

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # seconds — doubles each retry: 1s, 2s, 4s
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Rate limiter: Binance allows 1200 requests/minute
RATE_LIMIT_REQUESTS = 1200
RATE_LIMIT_WINDOW = 60  # seconds


# ------------------------------------------------------------------ #
#  Exceptions                                                          #
# ------------------------------------------------------------------ #


class BinanceAPIError(Exception):
    """Raised when Binance returns a recognised error response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceNetworkError(Exception):
    """Raised on connection / timeout / DNS failures."""


class RateLimitExceeded(BinanceAPIError):
    """Raised when the local rate limiter blocks a request."""

    def __init__(self) -> None:
        super().__init__(-1, "Local rate limit exceeded — too many requests.")


# ------------------------------------------------------------------ #
#  Rate Limiter                                                        #
# ------------------------------------------------------------------ #


class RateLimiter:
    """Thread-safe sliding-window rate limiter.

    Tracks timestamps of recent requests and blocks when the
    limit is exceeded within the window.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW,
    ) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until a request slot is available, or raise."""
        with self._lock:
            now = time.time()
            cutoff = now - self._window
            # Prune old timestamps
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self._max:
                logger.warning("Rate limit reached (%d/%d in %ds window)",
                               len(self._timestamps), self._max, self._window)
                raise RateLimitExceeded()

            self._timestamps.append(now)

    @property
    def remaining(self) -> int:
        """Approximate remaining requests in the current window."""
        with self._lock:
            now = time.time()
            cutoff = now - self._window
            active = sum(1 for t in self._timestamps if t > cutoff)
            return max(0, self._max - active)


# ------------------------------------------------------------------ #
#  Client                                                              #
# ------------------------------------------------------------------ #


class BinanceClient:
    """Low-level wrapper around the Binance Futures Testnet REST API.

    Parameters
    ----------
    api_key:
        Testnet API key.
    api_secret:
        Testnet API secret.
    base_url:
        Override the default testnet URL if needed.
    max_retries:
        Maximum number of retries for transient failures.
    enable_rate_limit:
        Whether to enforce local rate limiting.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        max_retries: int = MAX_RETRIES,
        enable_rate_limit: bool = True,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self._api_key,
        })
        self._rate_limiter = RateLimiter() if enable_rate_limit else None

    # ----- signing ------------------------------------------------- #

    def _sign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add ``timestamp`` and ``signature`` to *params*."""
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    # ----- HTTP helpers -------------------------------------------- #

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Any:
        """Execute an HTTP request with retry and rate limiting.

        Logs the request and response at DEBUG level; raises
        ``BinanceAPIError`` or ``BinanceNetworkError`` on failure.
        """
        last_exception: Exception | None = None

        for attempt in range(self._max_retries + 1):
            # Rate limiting
            if self._rate_limiter:
                self._rate_limiter.acquire()

            # Build fresh params each attempt (timestamp must be current)
            req_params = dict(params or {})
            if signed:
                req_params = self._sign(req_params)

            url = f"{self._base_url}{path}"
            logger.debug(
                "REQUEST  [attempt %d/%d] %s %s params=%s",
                attempt + 1, self._max_retries + 1, method, url, req_params,
            )

            try:
                resp = self._session.request(
                    method,
                    url,
                    params=req_params,
                    timeout=TIMEOUT,
                )
            except requests.exceptions.ConnectionError as exc:
                last_exception = BinanceNetworkError(f"Connection failed: {exc}")
                logger.warning("Network error (attempt %d): %s", attempt + 1, exc)
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exception from exc

            except requests.exceptions.Timeout as exc:
                last_exception = BinanceNetworkError(f"Request timed out: {exc}")
                logger.warning("Timeout (attempt %d): %s", attempt + 1, exc)
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue
                raise last_exception from exc

            except requests.exceptions.RequestException as exc:
                logger.error("Unexpected request error: %s", exc)
                raise BinanceNetworkError(f"Request error: {exc}") from exc

            logger.debug("RESPONSE %s %s", resp.status_code, resp.text[:500])

            # Retry on transient HTTP errors
            if resp.status_code in RETRYABLE_STATUS_CODES:
                logger.warning(
                    "Retryable HTTP %d (attempt %d/%d)",
                    resp.status_code, attempt + 1, self._max_retries + 1,
                )
                if attempt < self._max_retries:
                    self._backoff(attempt)
                    continue

            # Non-retryable errors
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                    raise BinanceAPIError(
                        body.get("code", resp.status_code),
                        body.get("msg", resp.text),
                    )
                except ValueError:
                    raise BinanceAPIError(resp.status_code, resp.text)

            return resp.json()

        # Exhausted all retries
        if last_exception:
            raise last_exception
        raise BinanceNetworkError("Request failed after all retries.")

    def _backoff(self, attempt: int) -> None:
        """Sleep with exponential backoff."""
        delay = RETRY_BACKOFF_BASE * (2 ** attempt)
        logger.info("Backing off %.1fs before retry...", delay)
        time.sleep(delay)

    # ----- Order API ----------------------------------------------- #

    def place_order(self, **params: Any) -> Dict[str, Any]:
        """POST /fapi/v1/order -- place a new futures order."""
        return self._request("POST", "/fapi/v1/order", params=params)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """DELETE /fapi/v1/order -- cancel an existing order."""
        return self._request("DELETE", "/fapi/v1/order", params={
            "symbol": symbol,
            "orderId": order_id,
        })

    def get_open_orders(self, symbol: str | None = None) -> List[Dict[str, Any]]:
        """GET /fapi/v1/openOrders -- all open orders (optionally per symbol)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/openOrders", params=params)

    def get_all_orders(
        self, symbol: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """GET /fapi/v1/allOrders -- order history for a symbol."""
        return self._request("GET", "/fapi/v1/allOrders", params={
            "symbol": symbol,
            "limit": limit,
        })

    # ----- Account API --------------------------------------------- #

    def get_account(self) -> Dict[str, Any]:
        """GET /fapi/v2/account -- account information."""
        return self._request("GET", "/fapi/v2/account")

    def get_balance(self) -> List[Dict[str, Any]]:
        """GET /fapi/v2/balance -- all asset balances."""
        return self._request("GET", "/fapi/v2/balance")

    def get_position_risk(self, symbol: str | None = None) -> List[Dict[str, Any]]:
        """GET /fapi/v2/positionRisk -- current positions."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v2/positionRisk", params=params)

    # ----- Market Data API ----------------------------------------- #

    def get_exchange_info(self) -> Dict[str, Any]:
        """GET /fapi/v1/exchangeInfo (unsigned)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_ticker_price(self, symbol: str | None = None) -> Any:
        """GET /fapi/v1/ticker/price -- latest price(s)."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/ticker/price", params=params, signed=False)

    def get_ticker_24h(self, symbol: str | None = None) -> Any:
        """GET /fapi/v1/ticker/24hr -- 24h statistics."""
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/fapi/v1/ticker/24hr", params=params, signed=False)
