"""
Binance Futures Testnet REST client.

Handles HMAC-SHA256 request signing, timestamping, and HTTP error
mapping.  Every request and response is logged at DEBUG level so the
log file provides a full audit trail.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://testnet.binancefuture.com"
TIMEOUT = 10  # seconds


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
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "X-MBX-APIKEY": self._api_key,
        })

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
    ) -> Dict[str, Any]:
        """Execute an HTTP request and return the JSON response.

        Logs the request and response at DEBUG level; raises
        ``BinanceAPIError`` or ``BinanceNetworkError`` on failure.
        """
        params = dict(params or {})
        if signed:
            params = self._sign(params)

        url = f"{self._base_url}{path}"
        logger.debug("REQUEST  %s %s params=%s", method, url, params)

        try:
            resp = self._session.request(
                method,
                url,
                params=params,
                timeout=TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            logger.error("Network error: %s", exc)
            raise BinanceNetworkError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s", exc)
            raise BinanceNetworkError(f"Request timed out: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected request error: %s", exc)
            raise BinanceNetworkError(f"Request error: {exc}") from exc

        logger.debug("RESPONSE %s %s", resp.status_code, resp.text[:500])

        # Binance returns JSON errors with {"code": …, "msg": …}
        if resp.status_code >= 400:
            try:
                body = resp.json()
                raise BinanceAPIError(body.get("code", resp.status_code), body.get("msg", resp.text))
            except ValueError:
                raise BinanceAPIError(resp.status_code, resp.text)

        return resp.json()

    # ----- public API methods -------------------------------------- #

    def place_order(self, **params: Any) -> Dict[str, Any]:
        """POST /fapi/v1/order — place a new futures order."""
        return self._request("POST", "/fapi/v1/order", params=params)

    def get_exchange_info(self) -> Dict[str, Any]:
        """GET /fapi/v1/exchangeInfo (unsigned)."""
        return self._request("GET", "/fapi/v1/exchangeInfo", signed=False)

    def get_account(self) -> Dict[str, Any]:
        """GET /fapi/v2/account — account information."""
        return self._request("GET", "/fapi/v2/account")
