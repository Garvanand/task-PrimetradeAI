"""
Tests for ``bot.client`` module.

Covers HMAC signing, HTTP success / error handling, retry logic,
and the sliding-window rate limiter.  Uses ``unittest.mock`` exclusively
(no ``responses`` library).
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest
import requests

from bot.client import (
    BinanceAPIError,
    BinanceClient,
    BinanceNetworkError,
    RateLimitExceeded,
    RateLimiter,
)


# ================================================================== #
#  Fixtures                                                            #
# ================================================================== #


@pytest.fixture()
def client() -> BinanceClient:
    """Return a ``BinanceClient`` with rate-limiting disabled."""
    return BinanceClient(
        api_key="test_key",
        api_secret="test_secret",
        enable_rate_limit=False,
    )


@pytest.fixture()
def client_with_retry() -> BinanceClient:
    """Return a ``BinanceClient`` with 1 retry and no rate limit."""
    return BinanceClient(
        api_key="test_key",
        api_secret="test_secret",
        enable_rate_limit=False,
        max_retries=1,
    )


# ================================================================== #
#  _sign                                                               #
# ================================================================== #


class TestSign:
    """Tests for ``BinanceClient._sign``."""

    @patch("bot.client.time.time", return_value=1700000000.0)
    def test_adds_timestamp_and_signature(self, mock_time: MagicMock, client: BinanceClient) -> None:
        """``_sign`` must inject ``timestamp`` and a valid HMAC-SHA256 ``signature``."""
        params = {"symbol": "BTCUSDT", "side": "BUY"}
        signed = client._sign(params)

        # Timestamp should be int(time * 1000)
        assert signed["timestamp"] == 1700000000000

        # Rebuild the expected signature independently
        expected_qs = urlencode({"symbol": "BTCUSDT", "side": "BUY", "timestamp": 1700000000000})
        expected_sig = hmac.new(
            b"test_secret",
            expected_qs.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        assert signed["signature"] == expected_sig

    @patch("bot.client.time.time", return_value=1700000000.0)
    def test_signature_changes_with_params(self, mock_time: MagicMock, client: BinanceClient) -> None:
        """Different parameters must produce different signatures."""
        sig_a = client._sign({"symbol": "BTCUSDT"})["signature"]
        sig_b = client._sign({"symbol": "ETHUSDT"})["signature"]
        assert sig_a != sig_b


# ================================================================== #
#  _request — success path                                             #
# ================================================================== #


class TestRequestSuccess:
    """Tests for successful HTTP requests."""

    @patch("bot.client.time.time", return_value=1700000000.0)
    @patch("requests.Session.request")
    def test_returns_json_on_200(
        self, mock_request: MagicMock, mock_time: MagicMock, client: BinanceClient
    ) -> None:
        """A 200 response with JSON body is returned as a dict."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"orderId": 12345}
        mock_response.text = '{"orderId": 12345}'
        mock_request.return_value = mock_response

        result = client._request("GET", "/fapi/v1/ticker/price", params={"symbol": "BTCUSDT"})

        assert result == {"orderId": 12345}
        mock_request.assert_called_once()


# ================================================================== #
#  _request — API error                                                #
# ================================================================== #


class TestRequestAPIError:
    """Tests for Binance API error responses."""

    @patch("bot.client.time.time", return_value=1700000000.0)
    @patch("requests.Session.request")
    def test_raises_binance_api_error_on_400(
        self, mock_request: MagicMock, mock_time: MagicMock, client: BinanceClient
    ) -> None:
        """A 400 response with Binance error JSON raises ``BinanceAPIError``."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"code": -1121, "msg": "Invalid symbol."}
        mock_response.text = '{"code": -1121, "msg": "Invalid symbol."}'
        mock_request.return_value = mock_response

        with pytest.raises(BinanceAPIError) as exc_info:
            client._request("GET", "/fapi/v1/ticker/price", params={"symbol": "BAD"})

        assert exc_info.value.code == -1121
        assert exc_info.value.message == "Invalid symbol."


# ================================================================== #
#  _request — network errors                                           #
# ================================================================== #


class TestRequestNetworkErrors:
    """Tests for network-level failures."""

    @patch("bot.client.time.time", return_value=1700000000.0)
    @patch("requests.Session.request", side_effect=requests.exceptions.ConnectionError("refused"))
    def test_connection_error_raises_network_error(
        self, mock_request: MagicMock, mock_time: MagicMock, client: BinanceClient
    ) -> None:
        """``ConnectionError`` is wrapped in ``BinanceNetworkError``."""
        with pytest.raises(BinanceNetworkError):
            client._request("GET", "/fapi/v1/ticker/price")

    @patch("bot.client.time.time", return_value=1700000000.0)
    @patch("requests.Session.request", side_effect=requests.exceptions.Timeout("timed out"))
    def test_timeout_raises_network_error(
        self, mock_request: MagicMock, mock_time: MagicMock, client: BinanceClient
    ) -> None:
        """``Timeout`` is wrapped in ``BinanceNetworkError``."""
        with pytest.raises(BinanceNetworkError):
            client._request("GET", "/fapi/v1/ticker/price")


# ================================================================== #
#  _request — retry on 500                                             #
# ================================================================== #


class TestRequestRetry:
    """Tests for retry behaviour on transient failures."""

    @patch("bot.client.time.sleep")  # prevent real sleeping
    @patch("bot.client.time.time", return_value=1700000000.0)
    @patch("requests.Session.request")
    def test_retry_on_500_then_success(
        self,
        mock_request: MagicMock,
        mock_time: MagicMock,
        mock_sleep: MagicMock,
        client_with_retry: BinanceClient,
    ) -> None:
        """First call returns 500, second returns 200 — should succeed."""
        response_500 = MagicMock()
        response_500.status_code = 500
        response_500.text = "Internal Server Error"

        response_200 = MagicMock()
        response_200.status_code = 200
        response_200.json.return_value = {"ok": True}
        response_200.text = '{"ok": true}'

        mock_request.side_effect = [response_500, response_200]

        result = client_with_retry._request("GET", "/fapi/v1/ticker/price")

        assert result == {"ok": True}
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once()  # one backoff sleep between attempts


# ================================================================== #
#  RateLimiter                                                         #
# ================================================================== #


class TestRateLimiter:
    """Tests for the sliding-window ``RateLimiter``."""

    def test_acquire_within_limit(self) -> None:
        """Acquiring up to ``max_requests`` times should succeed."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.acquire()  # 1st — OK
        limiter.acquire()  # 2nd — OK

    def test_acquire_exceeds_limit_raises(self) -> None:
        """Exceeding the limit raises ``RateLimitExceeded``."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.acquire()
        limiter.acquire()

        with pytest.raises(RateLimitExceeded):
            limiter.acquire()  # 3rd — should fail

    def test_remaining_property(self) -> None:
        """``remaining`` decreases as requests are consumed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.remaining == 5
        limiter.acquire()
        assert limiter.remaining == 4
        limiter.acquire()
        assert limiter.remaining == 3
