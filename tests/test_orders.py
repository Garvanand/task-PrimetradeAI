"""
Tests for ``bot.orders`` module.

Covers ``OrderManager`` methods (market, limit, stop-limit), the
``place_order`` dispatcher, and input-validation error paths.
The ``BinanceClient`` dependency is replaced with a ``MagicMock``.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.orders import OrderManager, OrderResult
from bot.validators import ValidationError


# ================================================================== #
#  Sample API responses                                                #
# ================================================================== #

MARKET_RESPONSE: dict = {
    "orderId": 12345,
    "symbol": "BTCUSDT",
    "side": "BUY",
    "type": "MARKET",
    "status": "FILLED",
    "origQty": "0.01",
    "executedQty": "0.01",
    "avgPrice": "67000.00",
    "price": "0",
    "stopPrice": "0",
    "timeInForce": "GTC",
}

LIMIT_RESPONSE: dict = {
    "orderId": 67890,
    "symbol": "ETHUSDT",
    "side": "SELL",
    "type": "LIMIT",
    "status": "NEW",
    "origQty": "1.5",
    "executedQty": "0",
    "avgPrice": "0",
    "price": "3500.00",
    "stopPrice": "0",
    "timeInForce": "GTC",
}

STOP_LIMIT_RESPONSE: dict = {
    "orderId": 99999,
    "symbol": "BTCUSDT",
    "side": "SELL",
    "type": "STOP",
    "status": "NEW",
    "origQty": "0.05",
    "executedQty": "0",
    "avgPrice": "0",
    "price": "64000.00",
    "stopPrice": "65000.00",
    "timeInForce": "GTC",
}


# ================================================================== #
#  Fixtures                                                            #
# ================================================================== #


@pytest.fixture()
def mock_client() -> MagicMock:
    """Return a ``MagicMock`` standing in for ``BinanceClient``."""
    return MagicMock()


@pytest.fixture()
def manager(mock_client: MagicMock) -> OrderManager:
    """Return an ``OrderManager`` wired to the mock client."""
    return OrderManager(client=mock_client)


# ================================================================== #
#  market_order                                                        #
# ================================================================== #


class TestMarketOrder:
    """Tests for ``OrderManager.market_order``."""

    def test_returns_correct_order_result(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """A successful MARKET order returns a populated ``OrderResult``."""
        mock_client.place_order.return_value = MARKET_RESPONSE

        result = manager.market_order("BTCUSDT", "BUY", 0.01)

        assert isinstance(result, OrderResult)
        assert result.order_id == 12345
        assert result.symbol == "BTCUSDT"
        assert result.side == "BUY"
        assert result.order_type == "MARKET"
        assert result.status == "FILLED"
        assert result.orig_qty == "0.01"
        assert result.executed_qty == "0.01"
        assert result.avg_price == "67000.00"
        assert result.price == "0"

    def test_calls_client_with_correct_params(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """``place_order`` is called with the expected keyword arguments."""
        mock_client.place_order.return_value = MARKET_RESPONSE

        manager.market_order("BTCUSDT", "BUY", 0.01)

        mock_client.place_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="BUY",
            type="MARKET",
            quantity=0.01,
        )


# ================================================================== #
#  limit_order                                                         #
# ================================================================== #


class TestLimitOrder:
    """Tests for ``OrderManager.limit_order``."""

    def test_returns_correct_order_result(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """A successful LIMIT order returns a populated ``OrderResult``."""
        mock_client.place_order.return_value = LIMIT_RESPONSE

        result = manager.limit_order("ETHUSDT", "SELL", 1.5, 3500.00)

        assert isinstance(result, OrderResult)
        assert result.order_id == 67890
        assert result.symbol == "ETHUSDT"
        assert result.side == "SELL"
        assert result.order_type == "LIMIT"
        assert result.status == "NEW"
        assert result.orig_qty == "1.5"
        assert result.price == "3500.00"
        assert result.time_in_force == "GTC"

    def test_calls_client_with_correct_params(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """``place_order`` is called with the expected keyword arguments including price."""
        mock_client.place_order.return_value = LIMIT_RESPONSE

        manager.limit_order("ETHUSDT", "SELL", 1.5, 3500.00)

        mock_client.place_order.assert_called_once_with(
            symbol="ETHUSDT",
            side="SELL",
            type="LIMIT",
            quantity=1.5,
            price=3500.00,
            timeInForce="GTC",
        )


# ================================================================== #
#  stop_limit_order                                                    #
# ================================================================== #


class TestStopLimitOrder:
    """Tests for ``OrderManager.stop_limit_order``."""

    def test_returns_correct_order_result(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """A successful STOP_LIMIT order returns a populated ``OrderResult``."""
        mock_client.place_order.return_value = STOP_LIMIT_RESPONSE

        result = manager.stop_limit_order("BTCUSDT", "SELL", 0.05, 64000.00, 65000.00)

        assert isinstance(result, OrderResult)
        assert result.order_id == 99999
        assert result.symbol == "BTCUSDT"
        assert result.side == "SELL"
        assert result.order_type == "STOP"
        assert result.status == "NEW"
        assert result.stop_price == "65000.00"
        assert result.price == "64000.00"

    def test_calls_client_with_correct_params(
        self, mock_client: MagicMock, manager: OrderManager
    ) -> None:
        """``place_order`` is called with stop-related keyword arguments."""
        mock_client.place_order.return_value = STOP_LIMIT_RESPONSE

        manager.stop_limit_order("BTCUSDT", "SELL", 0.05, 64000.00, 65000.00)

        mock_client.place_order.assert_called_once_with(
            symbol="BTCUSDT",
            side="SELL",
            type="STOP",
            quantity=0.05,
            price=64000.00,
            stopPrice=65000.00,
            timeInForce="GTC",
        )


# ================================================================== #
#  place_order dispatcher                                              #
# ================================================================== #


class TestPlaceOrderDispatcher:
    """Tests for the ``place_order`` dispatch method."""

    def test_dispatches_market(self, mock_client: MagicMock, manager: OrderManager) -> None:
        """``place_order(order_type='MARKET')`` routes to ``market_order``."""
        mock_client.place_order.return_value = MARKET_RESPONSE

        result = manager.place_order("BTCUSDT", "BUY", "MARKET", 0.01)

        assert result.order_type == "MARKET"
        assert result.order_id == 12345

    def test_dispatches_limit(self, mock_client: MagicMock, manager: OrderManager) -> None:
        """``place_order(order_type='LIMIT')`` routes to ``limit_order``."""
        mock_client.place_order.return_value = LIMIT_RESPONSE

        result = manager.place_order("ETHUSDT", "SELL", "LIMIT", 1.5, price=3500.00)

        assert result.order_type == "LIMIT"
        assert result.order_id == 67890

    def test_dispatches_stop_limit(self, mock_client: MagicMock, manager: OrderManager) -> None:
        """``place_order(order_type='STOP_LIMIT')`` routes to ``stop_limit_order``."""
        mock_client.place_order.return_value = STOP_LIMIT_RESPONSE

        result = manager.place_order(
            "BTCUSDT", "SELL", "STOP_LIMIT", 0.05,
            price=64000.00, stop_price=65000.00,
        )

        assert result.order_type == "STOP"
        assert result.order_id == 99999


# ================================================================== #
#  Validation errors                                                   #
# ================================================================== #


class TestValidationErrors:
    """Tests that invalid inputs are caught before reaching the client."""

    def test_invalid_symbol_in_market_order(self, manager: OrderManager) -> None:
        """An invalid symbol raises ``ValidationError`` in ``market_order``."""
        with pytest.raises(ValidationError):
            manager.market_order("", "BUY", 0.01)

    def test_invalid_symbol_in_limit_order(self, manager: OrderManager) -> None:
        """An invalid symbol raises ``ValidationError`` in ``limit_order``."""
        with pytest.raises(ValidationError):
            manager.limit_order("INVALID", "BUY", 0.01, 100.0)

    def test_missing_price_for_limit_order(self, manager: OrderManager) -> None:
        """Passing ``None`` as price for a LIMIT order raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            manager.limit_order("BTCUSDT", "BUY", 0.01, None)  # type: ignore[arg-type]

    def test_invalid_side(self, manager: OrderManager) -> None:
        """An invalid side raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            manager.market_order("BTCUSDT", "HOLD", 0.01)

    def test_invalid_quantity(self, manager: OrderManager) -> None:
        """A non-positive quantity raises ``ValidationError``."""
        with pytest.raises(ValidationError):
            manager.market_order("BTCUSDT", "BUY", -1)

    def test_invalid_order_type_in_dispatcher(self, manager: OrderManager) -> None:
        """An unsupported order type raises ``ValidationError`` in ``place_order``."""
        with pytest.raises(ValidationError):
            manager.place_order("BTCUSDT", "BUY", "FOK", 0.01)


# ================================================================== #
#  OrderResult.from_api_response                                       #
# ================================================================== #


class TestOrderResultFromAPIResponse:
    """Tests for the ``OrderResult.from_api_response`` classmethod."""

    def test_all_fields_mapped(self) -> None:
        """All API response keys are mapped to the correct dataclass fields."""
        result = OrderResult.from_api_response(MARKET_RESPONSE)

        assert result.order_id == 12345
        assert result.symbol == "BTCUSDT"
        assert result.side == "BUY"
        assert result.order_type == "MARKET"
        assert result.status == "FILLED"
        assert result.orig_qty == "0.01"
        assert result.executed_qty == "0.01"
        assert result.avg_price == "67000.00"
        assert result.price == "0"
        assert result.stop_price == "0"
        assert result.time_in_force == "GTC"
        assert result.raw == MARKET_RESPONSE

    def test_missing_keys_use_defaults(self) -> None:
        """Missing keys in the API response fall back to safe defaults."""
        result = OrderResult.from_api_response({})

        assert result.order_id == 0
        assert result.symbol == ""
        assert result.side == ""
        assert result.order_type == ""
        assert result.status == ""
